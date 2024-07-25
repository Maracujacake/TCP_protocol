import asyncio
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
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)

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
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao)
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
        self.cliente_seq_n = cliente_seq_n
        self.server_seq_n = 0 # número arbitrário, alterar se necessário
        self.seq_n_esperado = cliente_seq_n + 1 # número para verificar a ordem da conversação entre usuário e servidor
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.timer = asyncio.get_event_loop().call_later(1, self._exemplo_timer)
        #self.timer.cancel()   #é possível cancelar o timer chamando esse método

    def _exemplo_timer(self):
        print('Este é um exemplo de como fazer um timer')

    # envia um acknowledge/reconhecimento da tentativa de conexão
    def enviar_syn_ack(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        self.server_seq_n = 0 # modificar para um numero aleatorio posteriormente por segurança
        ack_n = self.cliente_seq_n + 1
        flags = FLAGS_SYN | FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, flags)
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.servidor.rede.enviar(segmento, dst_addr) 

    def enviar_ack(self, ack_n):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        flags = FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, ack_n, flags)
        self.servidor.rede.enviar(segmento, dst_addr)

    # seq_no = cliente_seq_n
    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        print('recebido payload: %r' % payload)

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
            self.seq_n_esperado += len(payload)
            self.enviar_ack(self.seq_n_esperado)
            if self.callback:
                self.callback(self, payload)

        # recebimento fora de ordem
        else:
            # envia sem alterar o n_esperado
            self.enviar_ack(self.seq_n_esperado)


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
        self.servidor.rede.enviar(segmento, dst_addr)
        """
        assim como adicionamos o tamanho do payload na função de recebimento,
        precisamos adicionar o tamanho do payload no numero de quem enviou também
        """
        self.server_seq_n += len(dados) 

    def fechar(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        flags = FLAGS_FIN | FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, self.seq_n_esperado, flags)
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.servidor.rede.enviar(segmento, dst_addr)
