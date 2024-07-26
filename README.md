# Camada de transporte – TCP

## Passo 1 - Estabelecimento de conexão

Para estabelecer uma conexão, determinado cliente envia a um servidor ou outra entidade um sinal "SYN" e um número que o representa.

Podemos interpretar isso como uma pessoa ligando para outra a partir de um telefonema

![image](https://github.com/user-attachments/assets/e935a0cc-fc49-4061-84e4-f84118e5e24b)

```python
#[...]
 # Estabelecer conexão
        if (flags & FLAGS_SYN) == FLAGS_SYN:
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao)
            # confirma estabelecimento de conexão
            conexao.enviar_syn_ack()
            if self.callback:
                self.callback(conexao)
#[...]

```
Quando você liga pra alguém, a pessoa que recebe a ligação, ao ver que o telefone está tocando, pode atender ou ignorar. Caso "atenda", a "pessoa" envia um sinal para outra (no caso do telefone, percebemos que alguém atendeu): "SYN+ACK"

![image](https://github.com/user-attachments/assets/5d5acbda-b206-4e7f-97e3-2a439c5f51d2)

```python
    def enviar_syn_ack(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        self.server_seq_n = 0 # modificar para um numero aleatorio posteriormente por segurança
        ack_n = self.cliente_seq_n + 1
        flags = FLAGS_SYN | FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, flags)
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.servidor.rede.enviar(segmento, dst_addr) 
```

O cliente por sua vez diz "Alô" quando o telefone é atendido, no nosso caso, envia uma confirmação de volta pro servidor pra dizer que, de fato, uma conexão foi estabelecida

![image](https://github.com/user-attachments/assets/7945ad00-96c4-4e3f-b8be-ef2ff7efb752)

```python
    def enviar_ack(self, ack_n):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        flags = FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, ack_n, flags)
        self.servidor.rede.enviar(segmento, dst_addr)
```

## Passo 2 - Recebimento de um payload

A vantagem de usar o protocolo TCP é a garantia de que os dados enviados chegarão inteiros e em ordem, para isso utilizamos
verificações constantes com base nos números que salvamos para as entidades que estão trocando dados

```python
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

```

Nas imagens do passo anterior, podemos observar que há coisas como "seq = A" ou "seq = B", vamos colocar isso como um número arbitrário.
Ele será necessário para irmos comparando o número de fato (no) com um número esperado (no_esperado) que seria ele (no) + o tamanho dos dados que recebeu. Se compararmos dessa forma, podemos garantir que, primeiro, os dados estão chegando em ordem:

Digamos que comecemos com o número do cliente e do servidor em 0, e, ao receber um payload de tamanho 100b do servidor, atualizamos o numero do cliente para 100, sabemos que o proximo payload tem que começar a partir do byte 100, caso contrário o numero não vai bater com o numero do cliente salvo. 

Segundamente podemos comparar se o arquivo foi totalmente recebido, afinal, no final da transferência, a diferença do numero inicial pro numero final do cliente (ou servidor) será o tamanho do arquivo

```python
    # seq_no = cliente_seq_n
    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
    #[...]
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
```
## Passo 3 — 1 ponto
Para completar esse passo precisamos, dentre algumas coisas, passar uma flag de ACKnowledge para confirmar o recebimento de um pacote,
só então criamos um cabeçalho com as informações de envio e os dados em si

```python
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

```

## Passo 4 — 1 ponto
Para encerramento de uma conexão utilizando protocolo TCP, é necessário que ambos os lados decidam encerrar e comuniquem-se sobre isso, quase como duas pessoas dizendo tchau no telefone.

![image](https://github.com/user-attachments/assets/c2f32c52-84f1-4e6f-bfee-c4b9574624e8)

Então, uma entidade envia a flag FIN com intuito de FINalizar a conexão, e o outro lado reconhece essa tentativa enviando uma flag de ACK em resposta.
O mesmo acontece com a outra entidade, envia uma flag FIN para ser respondida com um ACK

```python
def fechar(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        flags = FLAGS_FIN | FLAGS_ACK
        segmento = make_header(src_port, dst_port, self.server_seq_n, self.seq_n_esperado, flags)
        segmento = fix_checksum(segmento, src_addr, dst_addr)
        self.servidor.rede.enviar(segmento, dst_addr)
```

Só são enviadas informações padrões do cabeçalho (portas, endereços) e as flags que indicam o encerramento.

Para isso causar algum efeito, devemos adicionar uma verificação nas funções que tem responsabilidade de receber um pacote, A.K.A *rdt_rcv* de conexao

```python
def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        print('recebido payload: %r' % payload)

        if(flags & FLAGS_FIN) == FLAGS_FIN: 
            self.enviar_ack(seq_no + 1)
            if self.callback:
                self.callback(self, b'')
            return
        #[...]
``` 

## Passo 5 — 2 pontos

...
## Passo 6 — 2 pontos
...

## Passo 7 — 2 pontos
...


