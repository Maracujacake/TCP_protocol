import asyncio
from math import ceil
import time
# arquivo disponibilizado pelo prof. com funções que facilitam a implementação
from tcputils import *



class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {} # registra conexoes ativas
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, flags, window_size, checksum, urg_ptr = read_header(segment)

        # Consideramos somente a porta do nosso servidor
        if dst_port != self.porta:
            return
        if not self.rede.ignore_checksum and calc_checksum(segment, src_addr, dst_addr) != 0:
            print('Descartando segmento com "checksum" incorreto')
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port) # conexão única a ser salva em dicionário de conexões

        # Estabelecer conexão
        if (flags & FLAGS_SYN) == FLAGS_SYN:
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao, seq_no)
            # confirma estabelecimento de conexão
            conexao.enviar_syn_ack()
            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            # Passa para a conexão adequada se ela já estiver estabelecida
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    MSS = 1

    def __init__(self, servidor, id_conexao, cliente_seq_n):
        # identificadores para checagem de pacotes
        self.cliente_seq_n = cliente_seq_n
        self.server_seq_n = 0 # número arbitrário, alterar se necessário
        self.seq_n_esperado = cliente_seq_n + 1

        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None

        #congestionamento
        self.cwnd = Conexao.MSS # janela de congestionamento / congestion window
        self.ssthresh = 64 * Conexao.MSS

        # reenvio e reconhecimento de pacotes
        self.pacotes_nao_rec = {} # get(seq_no, valor_pacote)
        self.timer = None
        self.EstimatedRTT = None
        self.DevRTT = None
        self.G = 0.1 # Não passado em aula, é utilizado para suavização do tempo

    def _exemplo_timer(self):
        print('Este é um exemplo de como fazer um timer')

    def _temporizador(self):
        self.timer = None
        self.tamanho_janela = self.tamanho_janela/2

        # Verifica se a fila de segmentos enviados não está vazia.
        if self.fila_seguimentos_enviados:

            # Remove o primeiro elemento da fila e desempacota seus valores.
            segment, addr, len_dados = self.fila_seguimentos_enviados.popleft()[1:]

            # Adiciona uma nova tupla com 0 na frente da fila de segmentos enviados.
            self.fila_seguimentos_enviados.appendleft((0, segment, addr, len_dados))

            # Realiza a operação de envio do segmento para o endereço especificado.
            self.servidor.rede.enviar(segment, addr)

            # Configura um temporizador para chamar a função _temporizador após o intervalo de tempo especificado.
            self.timer = asyncio.get_event_loop().call_later(self.TimeoutInterval, self._temporizador)

    def iniciar_timer(self, intervalo):
        self.timer = asyncio.get_event_loop().call_later(intervalo, self.TimeoutOcorrido)

    def cancelar_timer(self):
        self.timer.cancel()
        self.timer = None
    
    def TimeoutInterval(self):
        # primeiro pacote a ser enviado
        if(self.EstimatedRTT == None or self.DevRTT == None):
            return 1.0
        
        return self.EstimatedRTT + max(self.G, 4 * self.DevRTT)

    def reenviar_pacotes(self):
        for segmento in self.pacotes_nao_rec.items():
            print("Reenviando segmento")
            self.servidor.rede.enviar(segmento, self.id_conexao[2])
        self.iniciar_timer(1)

    def TimeoutOcorrido(self):
        self.ssthresh = max(self.cwnd // 2, Conexao.MSS)
        self.cwnd = Conexao.MSS
        self.reenviar_pacotes() # após a reconfiguração da janela de congest., envia novamente o pacote

    # envia um acknowledge/reconhecimento da tentativa de conexão
    def enviar_syn_ack(self):
        print('Enviando SYN-ACK')
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        self.server_seq_n = 0 # modificar para um numero aleatorio posteriormente por segurança
        ack_n = self.cliente_seq_n + 1
        flags = FLAGS_SYN | FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, ack_n, flags)
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.servidor.rede.enviar(segmento, dst_addr) 


    def enviar_ack(self, ack_n):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        flags = FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, ack_n, flags)
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.servidor.rede.enviar(segmento, dst_addr)


    # seq_no = cliente_seq_n
    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        print('recebido payload: %r' % payload)
        if (flags & FLAGS_FIN == FLAGS_FIN):
            self.callback(self, b'')

            # Atualiza o número de sequência com o valor de "ack_no".
            self.seq_no_comprimento = ack_no

            src_addr, src_port, dst_addr, dst_port = self.id_conexao

            # Cria um segmento com base nos valores anteriores e as flags especificadas.
            segment = make_header(dst_port, src_port, self.seq_envio, self.seq_no_eperado + 1, flags)

            # Calcula o checksum do segmento e cria uma resposta com o checksum corrigido.
            response = fix_checksum(segment, dst_addr, src_addr)

            # Envia a resposta para o endereço de origem.
            self.servidor.rede.enviar(response, src_addr)

        # Verifica se o número de sequência recebido é igual ao esperado.
        elif seq_no == self.seq_no_eperado:
            # Atualiza o número de sequência esperado com o comprimento do payload, se houver.
            self.seq_no_eperado += (len(payload) if payload else 0)

            # Chama a função de retorno de chamada (callback) com o payload recebido.
            self.callback(self, payload)

            # Atualiza o número de sequência com o valor de "ack_no".
            self.seq_no_comprimento = ack_no

            # Verifica se a flag FLAGS_ACK está definida nos bits de "flags".
            if (flags & FLAGS_ACK) == FLAGS_ACK:

                # Verifica se o payload tem tamanho maior que 0.
                if payload:
                    src_addr, src_port, dst_addr, dst_port = self.id_conexao

                    # Cria um segmento com base nos valores anteriores e as flags especificadas.
                    segment = make_header(dst_port, src_port, self.seq_envio, self.seq_no_eperado, flags)

                    # Calcula o checksum do segmento e cria uma resposta com o checksum corrigido.
                    response = fix_checksum(segment, dst_addr, src_addr)

                    # Envia a resposta para o endereço de origem.
                    self.servidor.rede.enviar(response, src_addr)

                # Verifica se há segmentos na fila de segmentos enviados.
                existe_fila_segmentos_esperando = self.comprimento_seguimentos_enviados > 0

                # Cancela o temporizador se estiver ativo.
                if self.timer:
                    self.timer.cancel()
                    self.timer = None

                    # Procura na fila de segmentos enviados até encontrar um segmento com número de sequência igual a "ack_no".
                    while self.fila_seguimentos_enviados:
                        firstTime, segmento, _, len_dados = self.fila_seguimentos_enviados.popleft()
                        self.comprimento_seguimentos_enviados -= len_dados
                        seq = read_header(segmento)[2]
                        if seq == ack_no:
                            break

                    # Passo 6: Calcula SampleRTT, EstimatedRTT e DevRTT e atualiza o TimeoutInterval.
                    if firstTime:
                        self.SampleRTT = time.time() - firstTime
                        if self.checado == False:
                            self.checado = True
                            self.EstimatedRTT = self.SampleRTT
                            self.DevRTT = self.SampleRTT / 2
                        else:
                            self.EstimatedRTT = (1 - 0.125) * self.EstimatedRTT + 0.125 * self.SampleRTT
                            self.DevRTT = (1 - 0.25) * self.DevRTT + 0.25 * abs(self.SampleRTT - self.EstimatedRTT)
                        self.TimeoutInterval = self.EstimatedRTT + 4 * self.DevRTT

                # Verifica as condições "a" e "nenhum_comprimento_seguimentos_enviados" para ajustar a janela de congestionamento.
                nenhum_comprimento_seguimentos_enviados = self.comprimento_seguimentos_enviados == 0
                if existe_fila_segmentos_esperando and nenhum_comprimento_seguimentos_enviados:
                    self.tamanho_janela += MSS

                # Enquanto houver segmentos na fila de segmentos esperando e a janela permitir, envia segmentos.
                while self.fila_seguimentos_esperando:
                    response, src_addr, len_dados = self.fila_seguimentos_esperando.popleft()

                    if self.comprimento_seguimentos_enviados + len_dados > self.tamanho_janela:
                        self.fila_seguimentos_esperando.appendleft((response, src_addr, len_dados))
                        break

                    self.comprimento_seguimentos_enviados += len_dados
                    self.servidor.rede.enviar(response, src_addr)
                    self.fila_seguimentos_enviados.append((time.time(), response, src_addr, len_dados))

                # Se ainda houver segmentos na fila de segmentos enviados, configura o temporizador.
                if self.fila_seguimentos_enviados:
                    self.timer = asyncio.get_event_loop().call_later(self.TimeoutInterval, self._temporizador)


    # Os métodos abaixo fazem parte da API

    # envia dados a partir da conexao TCP estabelecida
    def enviar(self, dados):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        size = ceil(len(dados)/MSS)
        for i in range(size):
            self.seq_envio = self.seq_no_comprimento
            # Cria um segmento de rede com informações como portas, números de sequência e a flag de reconhecimento (ACK)
            segment = make_header(dst_port, src_port, self.seq_envio, self.seq_no_eperado, flags=FLAGS_ACK)
            segment += (dados[ i * MSS : min((i + 1) * MSS, len(dados))])

            # Registra o tamanho dos dados no segmento atual
            len_dados = len(dados[i * MSS : min((i + 1) * MSS, len(dados))])
            self.seq_no_comprimento += len_dados

            # Corrige o checksum do segmento antes de enviar
            response = fix_checksum(segment, dst_addr, src_addr)

            # Verifica se o segmento pode ser enviado com base na janela (tamanho_janela)
            if self.comprimento_seguimentos_enviados + len_dados <= self.tamanho_janela:
                # Envia o segmento para o servidor de rede
                self.servidor.rede.enviar(response, src_addr)

                # Registra o segmento enviado na fila de seguimentos enviados
                self.fila_seguimentos_enviados.append((time.time(), response, src_addr, len_dados))

                # Atualiza o comprimento total dos seguimentos enviados    
                self.comprimento_seguimentos_enviados += len_dados
                # Inicia um temporizador se necessário
                if not self.timer:
                    self.timer = asyncio.get_event_loop().call_later(self.TimeoutInterval, self._temporizador)
            else:
                # Se a janela estiver cheia, coloca o segmento na fila de espera
                self.fila_seguimentos_esperando.append((response, src_addr, len_dados))


    def fechar(self):

        # Atualiza o número de sequência a ser enviado
        self.seq_envio = self.seq_no_comprimento

        # Extrai informações sobre a conexão, como endereços e portas fonte e destino
        src_addr, src_port, dst_addr, dst_port = self.id_conexao

        # Cria um segmento de rede com informações como portas, números de sequência e a flag de finalização (FIN)
        segment = make_header(dst_port, src_port, self.seq_envio, self.seq_no_eperado + 1, FLAGS_FIN)

        # Calcula e corrige o checksum do segmento antes de enviar
        response = fix_checksum(segment, dst_addr, src_addr)

        # Envia o segmento de dados para o servidor de rede
        self.servidor.rede.enviar(response, src_addr)
