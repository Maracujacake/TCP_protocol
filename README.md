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
## Passo 3 — Envio de dados
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

## Passo 4 — Pausa e fechamento de conexões
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


## Passo 5 — Tratamento de perda de pacotes 
Como em uma comunicação, por qualquer que seja o motivo, informação (ou pacotes) podem ser perdidos, precisamos saber quando  isso ocorre e uma forma de tratar esse acontecimento.
Neste caso, usamos um timer. Ele tem a função de medir o tempo do momento que o pacote for enviado até ele ser recebido e, se determinada quantia de tempo passar sem que a confirmação do recebimento seja sinalizada, ele solta um "aviso" para que o pacote seja enviado novamente

![image](https://github.com/user-attachments/assets/0092a0b2-9bca-4931-bd77-c3b8f9a2cfe6)

Na imagem acima (Slide - 41, Kurose) podemos ver exatamente essa situação ocorrendo

Para isso, precisamos implementar uma função que inicie este timer e uma que o encerre para quando o pacote for recebido:
```python
    def iniciar_timer(self, intervalo):
        self.timer = asyncio.get_event_loop().call_later(intervalo, self.reenviar_pacotes_nao_reconhecidos)

    def cancelar_timer(self):
        self.timer.cancel()
        self.timer = None
```

Além disso, precisamos de uma função que reenviará os pacotes perdidos e precisamos iniciar esse timer no momento em que o pacote for enviado:

```python
    def reenviar_pacotes(self):
        for segmento in self.pacotes_nao_rec.items():
            print("Reenviando segmento")
            self.servidor.rede.enviar(segmento, self.id_conexao[2])
        self.iniciar_timer(1)
```

```python
    def enviar(self, dados):
        #[...]
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
```

Também chamamos a função que encerra o timer no eventual recebimento do pacote
```python
    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # [...]
        # recebimento do pacote concluido, retira-o do conjunto de pacotes não reconhecidos e para o timer
        if(ack_no > self.server_seq_n):
            self.server_seq_n = ack_no
            if(ack_no in self.pacotes_nao_rec):
                del self.pacotes_nao_rec[ack_no]
            # cancela o timer para evitar possíveis retransmissões
            self.cancelar_timer()
```
Lembrando que adicionamos um dicionário de pacotes_não_reconhecidos em Conexão

## Passo 6 — Tempo de tolerância para perda de pacotes
Como podemos inferir quanto tempo é adequado para que um pacote seja dado como "Deu ruim, tem que enviar de novo"? Não podemos escolher um número arbitrário como, sei lá, 1 segundo. Imagine que estamos tratando de pacotes de informações ENORMES que não teriam como ser enviados em um segundo.. daria problema. Para isso, podemos medir um tempo adequado utilizando o seguinte:

![image](https://github.com/user-attachments/assets/8b40f889-2181-4f0d-b085-9297009f8fa1)

Sendo:

EstimatedRTT = (1 - alpha) * EstimatedRTT + alpha * sample_rtt,

DevRTT = (1 - beta) * DevRTT + beta * abs(sample_rtt - self.EstimatedRTT)

Definimos então a função e a atualizamos conforme os pacotes forem sendo recebidos, lembrando que no primeiro a ser enviado/recebido utilizamos um valor fixo, afinal não dá pra ter uma noção sem pelo menos UM pacote ter sido enviado

```python
    def TimeoutInterval(self):
        # primeiro pacote a ser enviado
        if(self.EstimatedRTT == None or self.DevRTT == None):
            return 1.0
        
        return self.EstimatedRTT + max(self.G, 4 * self.DevRTT) # volta o valor de DevRTT na maior parte das vezes
```

```python
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
#[...]
```


## Passo 7 — 2 pontos
...


