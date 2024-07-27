import asyncio
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

        print(f'Received segment from {src_addr}:{src_port} to {dst_addr}:{dst_port}')
        # Consideramos somente a porta do nosso servidor
        if dst_port != self.porta:
            return
        if not self.rede.ignore_checksum and calc_checksum(segment, src_addr, dst_addr) != 0:
            print('descartando segmento com checksum incorreto')
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port) # conexão única a ser salva em dicionário de conexões

        # Estabelecer conexão
        if (flags & FLAGS_SYN) == FLAGS_SYN:
            print(f'Estabelecendo conexão com {src_addr}:{src_port}')
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
    def __init__(self, servidor, id_conexao, cliente_seq_n):
        # identificadores para checagem de pacotes
        self.cliente_seq_n = cliente_seq_n
        self.server_seq_n = 0 # número arbitrário, alterar se necessário
        self.seq_n_esperado = cliente_seq_n + 1

        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None

        # reenvio e reconhecimento de pacotes
        self.pacotes_nao_rec = {} # get(seq_no, valor_pacote)
        self.timer = None
        self.EstimatedRTT = None
        self.DevRTT = None
        self.G = 0.1 # Não passado em aula, é utilizado para suavização do tempo

    def _exemplo_timer(self):
        print('Este é um exemplo de como fazer um timer')

    def iniciar_timer(self, intervalo):
        self.timer = asyncio.get_event_loop().call_later(intervalo, self.reenviar_pacotes_nao_reconhecidos)

    def cancelar_timer(self):
        self.timer.cancel()
        self.timer = None
    
    def TimeoutInterval(self):
        # primeiro pacote a ser enviado
        if(self.EstimatedRTT == None or self.DevRTT == None):
            return 1.0
        
        return self.EstimatedRTT + max(self.G, 4 * self.DevRTT) # volta o valor de DevRTT na maior parte das vezes

    def reenviar_pacotes(self):
        for segmento in self.pacotes_nao_rec.items():
            print("Reenviando segmento")
            self.servidor.rede.enviar(segmento, self.id_conexao[2])
        self.iniciar_timer(1)

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

        if(ack_no in self.pacotes_nao_rec):
            # tempo que demorou para o pacote ser transmitido
            sample_rtt = time.time() - self.envio_inicio

            # caso seja o primeiro pacote a ser transmitido
            if(self.EstimatedRTT == None):
                self.EstimatedRTT = sample_rtt
                self.DevRTT = sample_rtt / 2

            #atualiza os valores com base no tempo de transmissao
            else:
                alpha = 0.125
                beta = 0.25
                self.EstimatedRTT = (1 - alpha) * self.EstimatedRTT + alpha * sample_rtt
                self.DevRTT = (1 - beta) * self.DevRTT + beta * abs(sample_rtt - self.EstimatedRTT)

            # inicia o timer com o novo padrão
            self.cancelar_timer()
            self.iniciar_timer(self.TimeoutInterval)

            # retira o pacote da lista de não reconhecidos
            del self.pacotes_nao_rec[ack_no]

        if(flags & FLAGS_FIN) == FLAGS_FIN: 
            self.enviar_ack(seq_no + 1)
            if self.callback:
                self.callback(self, b'')
            return

        """
        numero de confirmação do cliente for igual ao esperado (número dele + 1), 
        o pacote está sendo recebido em ordem
        """
        if(seq_no == self.seq_n_esperado):
            """
            adiciona no n_esperado o tamanho do payload, para que na proxima vez que seja recebido outro,
            seja possível compararmos se está em ordem
            ex: não tínhamos recebido payload algum então digamos que o n_esperado esteja em 1 (0 + 1 do acknowledge)
            - ao receber um payload de 100 bytes, passa a ser 101
            - proximo payload que começa no 101 (ou no 100 pq começa em 0?) vai verificar o número esperado pra ver se bate
            """
            if self.callback:
                self.callback(self, payload)
            self.seq_n_esperado += len(payload)
            self.enviar_ack(self.seq_n_esperado)
        # recebimento fora de ordem
        else:
            # envia sem alterar o n_esperado
            self.enviar_ack(self.seq_n_esperado)

        # recebimento do pacote concluido, retira-o do conjunto de pacotes não reconhecidos e para o timer
        if(ack_no > self.server_seq_n):
            self.server_seq_n = ack_no
            if(ack_no in self.pacotes_nao_rec):
                del self.pacotes_nao_rec[ack_no]
            # cancela o timer para evitar possíveis retransmissões
            self.cancelar_timer()


    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        self.callback = callback

    # envia dados a partir da conexao TCP estabelecida
    def enviar(self, dados):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        flags = FLAGS_ACK
        # passamos o numero que caracteriza o servidor/recebedor e o numero esperado do cliente que vai receber
        segmento = make_header(src_port, dst_port, self.server_seq_n, self.seq_n_esperado, flags)
        segmento += dados
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.envio_inicio = time.time()
        self.servidor.rede.enviar(segmento, dst_addr)
        """
        assim como adicionamos o tamanho do payload na função de recebimento,
        precisamos adicionar o tamanho do payload no numero de quem enviou também
        """
        self.pacotes_nao_rec[self.server_seq_n] = segmento
        self.server_seq_n += len(dados)

        # inicia timer para reenvio se necessario.
        self.iniciar_timer(self.TimeoutInterval())


    def fechar(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        flags = FLAGS_FIN | FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, self.seq_n_esperado, flags)
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.servidor.rede.enviar(segmento, dst_addr)
