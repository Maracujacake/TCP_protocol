# Camada de transporte – TCP

## Passo 1 - Estabelecimento de conexão

Para estabelecer uma conexão, determinado cliente envia a um servidor ou outra entidade um sinal "SYN" e um número que o representa.

Podemos interpretar isso como uma pessoa ligando para outra a partir de um telefonema

![image](https://github.com/user-attachments/assets/e935a0cc-fc49-4061-84e4-f84118e5e24b)

O recebimento do "telefonema" é mostrado abaixo, aonde um cliente tenta estabelecer uma conexão com o servidor a partir da flag SYN

```python
#[...]
#Estabelecimento de conexão
 if (flags & FLAGS_SYN) == FLAGS_SYN:
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao, seq_no, ack_no)

            # Numero arbitrario
            seq_envio = random.randint(0, 0xffff)
            # Atribua o próximo número de sequência esperado pelo dispositivo receptor
            ack_envio = seq_no + 1
            # Construa um segmento com SYN+ACK
            segment = make_header(dst_port, src_port, seq_envio, ack_envio, FLAGS_SYN | FLAGS_ACK)
            # Corrija o checksum do segmento
            response = fix_checksum(segment, dst_addr, src_addr)
            # Envie o segmento de resposta
            self.rede.enviar(response, src_addr)
#[...]

```
Quando você liga pra alguém, a pessoa que recebe a ligação, ao ver que o telefone está tocando, pode atender ou ignorar. Caso "atenda", a "pessoa" envia um sinal para outra (no caso do telefone, percebemos que alguém atendeu): "SYN+ACK"

![image](https://github.com/user-attachments/assets/5d5acbda-b206-4e7f-97e3-2a439c5f51d2)

```python
[...]
     # Construa um segmento com SYN+ACK
            segment = make_header(dst_port, src_port, seq_envio, ack_envio, FLAGS_SYN | FLAGS_ACK)
            # Corrija o checksum do segmento
            response = fix_checksum(segment, dst_addr, src_addr)
            # Envie o segmento de resposta
            self.rede.enviar(response, src_addr)
[...]
```

O cliente por sua vez diz "Alô" quando o telefone é atendido, no nosso caso, envia uma confirmação de volta pro servidor pra dizer que, de fato, uma conexão foi estabelecida

![image](https://github.com/user-attachments/assets/7945ad00-96c4-4e3f-b8be-ef2ff7efb752)

```python
    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
            [...]
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
            [...]
```

## Passo 2 - Recebimento de um payload

A vantagem de usar o protocolo TCP é a garantia de que os dados enviados chegarão inteiros e em ordem, para isso utilizamos
verificações constantes com base nos números que salvamos para as entidades que estão trocando dados

```python
class Conexao:
    # Adicionado seq_no e ack_no
    def __init__(self, servidor, id_conexao, seq_no, ack_no):
        self.servidor = servidor # Servidor que estaremos em conexao
        self.id_conexao = id_conexao # o id da conexão entre as conexões
        self.callback = None
        self.seq_envio = random.randint(0, 0xffff) # numero arbitrario para envio
        self.seq_no_eperado = seq_no + 1 # numero de recebimento esperado (numero da sequencia + 1)
        self.seq_no_comprimento = ack_no
        self.fila_seguimentos_enviados = deque() # filas de pacotes enviados e recebidos
        self.fila_seguimentos_esperando = deque()
        [...]
```

Nas imagens do passo anterior, podemos observar que há coisas como "seq = A" ou "seq = B", vamos colocar isso como um número arbitrário.
Ele será necessário para irmos comparando o número de fato (no) com um número esperado (no_esperado) que seria ele (no) + o tamanho dos dados que recebeu. Se compararmos dessa forma, podemos garantir que, primeiro, os dados estão chegando em ordem:

Digamos que comecemos com o número do cliente e do servidor em 0, e, ao receber um payload de tamanho 100b do servidor, atualizamos o numero do cliente para 100, sabemos que o proximo payload tem que começar a partir do byte 100, caso contrário o numero não vai bater com o numero do cliente salvo. 

Segundamente podemos comparar se o arquivo foi totalmente recebido, afinal, no final da transferência, a diferença do numero inicial pro numero final do cliente (ou servidor) será o tamanho do arquivo

```python
[...]
        elif seq_no == self.seq_no_eperado:
            self.seq_no_eperado += (len(payload) if payload else 0)

            # Chama a função de retorno de chamada (callback) com o payload recebido.
            self.callback(self, payload)

            # Atualiza o número de sequência com o valor de "ack_no".
            self.seq_no_comprimento = ack_no
[...]
```
## Passo 3 — Envio de dados
Para completar esse passo precisamos, dentre algumas coisas, passar uma flag de ACKnowledge para confirmar o recebimento de um pacote,
só então criamos um cabeçalho com as informações de envio e os dados em si

```python
    def enviar(self, dados):
            [...]
            # Cria um segmento de rede com informações como portas, números de sequência e a flag de reconhecimento (ACK)
            segment = make_header(dst_port, src_port, self.seq_envio, self.seq_no_eperado, flags=FLAGS_ACK)
            segment += (dados[ i * MSS : min((i + 1) * MSS, len(dados))])
            [...]
            # Corrige o checksum do segmento antes de enviar
            response = fix_checksum(segment, dst_addr, src_addr)

```

## Passo 4 — Pausa e fechamento de conexões
Para encerramento de uma conexão utilizando protocolo TCP, é necessário que ambos os lados decidam encerrar e comuniquem-se sobre isso, quase como duas pessoas dizendo tchau no telefone.

![image](https://github.com/user-attachments/assets/c2f32c52-84f1-4e6f-bfee-c4b9574624e8)

Então, uma entidade envia a flag FIN com intuito de FINalizar a conexão, e o outro lado reconhece essa tentativa enviando uma flag de ACK em resposta.
O mesmo acontece com a outra entidade, envia uma flag FIN para ser respondida com um ACK

```python
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
```

Só são enviadas informações padrões do cabeçalho (portas, endereços) e as flags que indicam o encerramento.

Para isso causar algum efeito, devemos adicionar uma verificação nas funções que tem responsabilidade de receber um pacote, A.K.A *rdt_rcv* de conexao

```python
def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # Verifica se a flag FLAGS_FIN está definida nos bits de "flags".
        if (flags & FLAGS_FIN == FLAGS_FIN):

            # Chama a função de retorno de chamada (callback) com uma sequência vazia.
            self.callback(self, b'')

            # Atualiza o número de sequência com o valor de "ack_no".
            self.seq_no_comprimento = ack_no

            # Desempacota o endereço de origem, porta de origem, endereço de destino e porta de destino da conexão.
            src_addr, src_port, dst_addr, dst_port = self.id_conexao

            # Cria um segmento com base nos valores anteriores e as flags especificadas.
            segment = make_header(dst_port, src_port, self.seq_envio, self.seq_no_eperado + 1, flags)

            # Calcula o checksum do segmento e cria uma resposta com o checksum corrigido.
            response = fix_checksum(segment, dst_addr, src_addr)

            # Envia a resposta para o endereço de origem.
            self.servidor.rede.enviar(response, src_addr)
        #[...]
```


## Passo 5 — Tratamento de perda de pacotes 
Como em uma comunicação, por qualquer que seja o motivo, informação (ou pacotes) podem ser perdidos, precisamos saber quando  isso ocorre e uma forma de tratar esse acontecimento.
Neste caso, usamos um timer. Ele tem a função de medir o tempo do momento que o pacote for enviado até ele ser recebido e, se determinada quantia de tempo passar sem que a confirmação do recebimento seja sinalizada, ele solta um "aviso" para que o pacote seja enviado novamente

![image](https://github.com/user-attachments/assets/0092a0b2-9bca-4931-bd77-c3b8f9a2cfe6)

Na imagem acima (Slide - 41, Kurose) podemos ver exatamente essa situação ocorrendo

Para isso, precisamos implementar uma função que inicie este timer e uma que o encerre para quando o pacote for recebido:
```python
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
```

Para encerrar o timer no eventual recebimento do pacote
```python
    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # [...]
        # Cancela o temporizador se estiver ativo.
        if self.timer:
           self.timer.cancel()
           self.timer = None
```

## Passo 6 — Tempo de tolerância para perda de pacotes
Como podemos inferir quanto tempo é adequado para que um pacote seja dado como "Deu ruim, tem que enviar de novo"? Não podemos escolher um número arbitrário como, sei lá, 1 segundo. Imagine que estamos tratando de pacotes de informações ENORMES que não teriam como ser enviados em um segundo.. daria problema. Para isso, podemos medir um tempo adequado utilizando o seguinte:

![image](https://github.com/user-attachments/assets/8b40f889-2181-4f0d-b085-9297009f8fa1)

Sendo:

EstimatedRTT = (1 - alpha) * EstimatedRTT + alpha * sample_rtt,

DevRTT = (1 - beta) * DevRTT + beta * abs(sample_rtt - self.EstimatedRTT)

Atualizamos conforme os pacotes forem sendo recebidos, lembrando que no primeiro a ser enviado/recebido utilizamos um valor fixo, afinal não dá pra ter uma noção sem pelo menos UM pacote ter sido enviado

```python
[...]
#Calcula SampleRTT, EstimatedRTT e DevRTT e atualiza o TimeoutInterval.
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
```

## Passo 7 — Janela de congestionamento
Quando enviamos arquivos muito grandes ou então muitos arquivos estão sendo enviados, pode ser que acabe gerando congestionamento na rede (podendo ocasionar em lentidão, perda de pacotes, etc). Para evitar isso, utilizamos uma "janela" de congestionamento, isto é, um intervalo de "tamanho" de dados que serão enviados e devem ser sinalizados como recebidos para enviar uma nova parcela de dados do mesmo tamanho ou gradualmente maior

![image](https://github.com/user-attachments/assets/1c65d82a-9a1b-4d0d-9c49-c91147e5d9c2)

Na imagem acima podemos ver o estado de slow start, isto é, conforme os primeiros pacotes vão sendo enviados, o tamanho da janela (colocamos como 1) vai aumentando gradualmente em pequenos valores e quando atingir um ápice, que consideramos aqui como 64 (64 * 1 = 64), o aumento se torna ainda maior

```python
#[...]
   self.tamanho_janela = 1 * MSS
#[...]
   if existe_fila_segmentos_esperando and nenhum_comprimento_seguimentos_enviados:
      self.tamanho_janela += MSS
#[...]
```


```python
        size = ceil(len(dados)/MSS)
        for i in range(size):
            self.seq_envio = self.seq_no_comprimento
            # Cria um segmento de rede com informações como portas, números de sequência e a flag de reconhecimento (ACK)
            segment = make_header(dst_port, src_port, self.seq_envio, self.seq_no_eperado, flags=FLAGS_ACK)
            segment += (dados[ i * MSS : min((i + 1) * MSS, len(dados))])

            # Registra o tamanho dos dados no segmento atual
            len_dados = len(dados[i * MSS : min((i + 1) * MSS, len(dados))])
```

A janela aumenta conforme o envio dos dados é bem sucedido. Se por acaso, houver congestionamento, ou melhor, o tamanho/quantidade de envio for maior ou igual à janela, os envios devem ser parados até que os anteriores sejam completados abrindo espaço.
