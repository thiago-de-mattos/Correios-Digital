# Correios Digital

Sistema de mensageria segura: as mensagens ficam criptografadas e organizadas
numa árvore binária de busca autobalanceada (AVL).

Projeto integrado das disciplinas de **Estrutura de Dados Avançada** e
**Processo de Desenvolvimento de Software**.

---

## Como rodar

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python3 scripts/servidor.py         # abre o sistema no navegador
pytest                              # roda os testes
python3 scripts/height_demo.py      # demonstração da Sprint 1
python3 scripts/messaging_demo.py   # demonstração da Sprint 2
python3 scripts/backup_demo.py      # demonstração da Sprint 3
```

---

## Estrutura de pastas

```
digital-post-office/
├── src/postoffice/
│   ├── structures/      # a árvore AVL
│   ├── security/        # hash de senha, cofre simétrico e chaves RSA
│   ├── domain/          # entidades: Usuario e Mensagem
│   ├── services/        # conversa, chaveiro, mensageria e autenticação
│   ├── persistence/     # arquivo, pen drive, e-mail
│   └── presentation/    # Flask, telas e plotagem
├── tests/
├── scripts/
└── docs/
```

O código fica em `src/` em vez da raiz (*src layout*). Sem isso,
`import postoffice` pega a pasta do repositório mesmo quando o pacote não foi
instalado, e um teste pode passar na máquina de quem escreveu e falhar na de
outra pessoa.

### Regra de dependência

As setas apontam sempre para baixo. Nenhum módulo importa quem está acima dele.

```
presentation  ->  services  ->  domain  ->  security
                            \
                             ->  structures
```

- **`structures`** e **`security`** não importam nada do projeto.
- **`domain`** conhece `security` (para cifrar) mas **não** conhece
  `structures`: a mensagem não sabe que existe uma árvore. Quem junta os dois
  é `services`.
- **`persistence`** e **`presentation`** ficam nas bordas, onde estão o disco,
  a rede e a tela.

### Convenção de nomes

Pastas e arquivos em inglês, seguindo a prática comum de repositórios
públicos. O código em si — classes, métodos e variáveis — em português,
acompanhando a documentação, os casos de uso e o quadro de tarefas.

| Arquivo | Conteúdo |
|---|---|
| `structures/avl_tree.py` | `ArvoreAVL`, `No`, rotações e percursos |
| `security/passwords.py` | `gerar_salt`, `calcular_hash`, `conferir` |
| `security/vault.py` | `Cofre`, `cifrar`, `decifrar` |
| `security/keys.py` | `gerar_par`, `cifrar_chave`, `impressao_digital` |
| `services/keyring.py` | `Chaveiro` — árvore AVL de chaves públicas |
| `persistence/serializer.py` | árvore ↔ JSON, em pré-ordem |
| `persistence/repository.py` | `Repositorio` — grava e lê os arquivos |
| `persistence/backup.py` | `exportar`, `importar`, `conferir` |
| `persistence/mailer.py` | `enviar_backup` via SMTP |
| `presentation/app.py` | rotas Flask e API entre máquinas |
| `presentation/plot.py` | `arvore_para_svg` — desenho da AVL |
| `presentation/network.py` | `ClienteRede` — fala com a outra máquina |
| `domain/message.py` | `Mensagem`, `ChaveMensagem`, `gerar_chave` |
| `domain/user.py` | `Usuario`, `cadastrar`, `entrar` |

---

## Decisões técnicas

### Por que AVL e não uma BST comum

A chave de cada mensagem é o instante do envio. Como as mensagens chegam
sempre com horário crescente, uma árvore de busca comum insere tudo à direita
e vira uma lista encadeada.

Medido em `scripts/height_demo.py`, com 10.000 mensagens:

| Estrutura | Altura | Comparações para achar uma mensagem |
|---|---|---|
| BST comum | 10.000 | até 10.000 |
| AVL | 14 | até 14 |

### Chave composta

A chave é a tupla `(instante, sequencia)`. Duas mensagens no mesmo segundo
desempatam pelo contador. Tuplas em Python comparam campo a campo, então a
ordenação sai de graça.

Os instantes são gravados em **UTC**. Horário local muda com fuso e horário de
verão, e isso bagunçaria a ordem do histórico.

### Autenticação e criptografia são coisas separadas

Os dois nascem da senha do usuário, mas com **salts diferentes**:

| | Para quê | Como |
|---|---|---|
| `salt_autenticacao` | conferir o login | PBKDF2-HMAC-SHA256, 600.000 iterações |
| `salt_cofre` | cifrar as mensagens | PBKDF2 → chave Fernet (AES + HMAC) |

Se os dois fossem o mesmo valor, quem roubasse o arquivo de usuários
conseguiria decifrar as mensagens.

O Fernet foi escolhido porque já embute HMAC de integridade: arquivo
adulterado é detectado sozinho.

### Criptografia híbrida: RSA por cima, Fernet por baixo

Cada usuário gera um par de chaves RSA-2048 no cadastro. A pública circula
livremente; a privada fica guardada em PEM cifrado pela senha do dono e só é
aberta no login.

Cada mensagem é cifrada assim:

1. gera-se uma chave simétrica nova, só para aquela mensagem
2. o texto é cifrado com ela, usando Fernet
3. essa chave é cifrada duas vezes com RSA-OAEP: uma com a pública do
   destinatário, outra com a do remetente

A segunda cópia existe para o remetente conseguir reler o próprio histórico.
Sem ela, você manda a mensagem e nunca mais vê o que escreveu.

RSA puro seria lento e tem limite de tamanho; Fernet puro exigiria combinar uma
senha por fora. O modelo híbrido é o que TLS e Signal usam.

### Por que não uma senha combinada entre as partes

Uma frase compartilhada precisaria ser transmitida de alguma forma — telefone,
e-mail, mensagem. Seria o mesmo canal que o cliente não confia, e o problema
original voltaria pela porta dos fundos.

Com par de chaves, a chave pública pode ser interceptada, copiada ou publicada
sem consequência. Ela só serve para fechar.

**Limitação conhecida:** se alguém interceptar a troca inicial e substituir a
chave pública por uma própria, o remetente cifra para o atacante sem perceber
(ataque *man-in-the-middle*). A defesa implementada é a **impressão digital**:
`Chaveiro.impressao_digital(login)` devolve oito grupos de quatro caracteres
que os dois lados conferem por um canal independente — o mesmo mecanismo do
código de segurança do WhatsApp. A solução completa exigiria uma autoridade
certificadora, fora do escopo do projeto.

### Persistência: pré-ordem e JSON cifrado

A árvore é gravada percorrida em **pré-ordem**. Relendo nessa mesma ordem, cada
nó cai exatamente onde estava e a árvore é reconstruída com a forma idêntica —
nenhuma rotação é disparada, porque a sequência já vem de uma AVL válida. Um
teste confere isso comparando o percurso em pré-ordem antes e depois.

O que vai em cada arquivo:

| Arquivo | Conteúdo | Cifrado? |
|---|---|---|
| `usuarios.json` | hash da senha, salts, chave pública, chave privada em PEM cifrado | a privada já vem cifrada pela senha |
| `chaveiro.json` | chaves públicas dos contatos | não precisa: são públicas |
| `<login>/conversas/<id>.cofre` | a árvore de mensagens inteira | sim, pelo cofre pessoal do dono |

As mensagens já estão cifradas individualmente. O arquivo de conversa é cifrado
de novo por cima para esconder os **metadados**: com quem se falou, quando e
quantas vezes. Um pen drive perdido não revela nem o conteúdo nem o padrão.

A gravação passa por um arquivo `.tmp` que depois é renomeado. Se faltar energia
no meio, o arquivo antigo continua íntegro em vez de ficar pela metade.

Não usamos `pickle`: carregar um pickle executa código do arquivo, e um backup
adulterado viraria execução remota. JSON só carrega dados.

### Onde o texto legível existe

Só dentro de uma variável local, durante a exibição. A entidade `Mensagem` não
tem atributo com o texto puro — ela guarda apenas `conteudo_cifrado`.

A chave privada vive na `Sessao` e é descartada no `sair()`. Depois disso,
qualquer acesso levanta `SessaoEncerradaError`.

### Dois pontos que exigem atenção ao mexer

Em `_rotacionar_direita` e `_rotacionar_esquerda`, a ordem das chamadas de
`_atualizar_altura` não é arbitrária: o nó que desceu vem primeiro. Invertido,
a árvore continua funcionando e vai desbalanceando devagar.

Em `_rebalancear`, a escolha da rotação olha o fator de balanceamento do
filho, não a chave inserida. É isso que faz a mesma função servir para
`inserir` e para `remover`.

---

## Status por sprint

| Sprint | Escopo | Situação |
|---|---|---|
| 1 | Árvore AVL, cadastro, login, hash de senha | concluída |
| 2 | Mensagens, criptografia, histórico, busca, remoção | concluída |
| 3 | Persistência, backup, pen drive, e-mail | concluída |
| 4 | Plotagem, interface, documentação | concluída |

---

## Como usar em duas máquinas

Cada pessoa roda o próprio servidor. Não existe máquina central.

```bash
python3 scripts/servidor.py --porta 5000 --dados dados
```

O programa imprime dois endereços: `localhost` para você, e o IP da rede para
passar aos colegas. Abra o `localhost` no navegador, crie sua conta, e em
**Contatos** informe o endereço da outra máquina.

O sistema busca a identidade do outro lado e mostra a **impressão digital** da
chave pública. Confiram os 32 caracteres por voz antes de confirmar — é a defesa
contra alguém trocar a chave no meio do caminho.

### As telas

| Rota | O que faz |
|---|---|
| `/cadastro` | cria a conta e gera o par de chaves |
| `/login` | abre a chave privada e carrega as conversas do disco |
| `/` | lista de contatos e conversas |
| `/conversa/<login>` | histórico e envio |
| `/contatos` | descobrir, conferir impressão digital e adicionar |
| `/arvore/<login>` | desenho da AVL daquela conversa |
| `/backup` | exportar, restaurar e enviar por e-mail |

### A API entre máquinas

| Rota | Uso |
|---|---|
| `GET /api/identidade` | devolve login, chave pública e impressão digital |
| `POST /api/mensagens` | recebe uma mensagem cifrada de outra máquina |

`POST /api/mensagens` só aceita mensagem de remetente que já esteja no chaveiro.
Como o conteúdo vem cifrado para a chave pública do destinatário, o transporte
não precisa ser confiável.

### A plotagem

O desenho é SVG gerado em Python, sem biblioteca gráfica. A posição de cada nó
sai da própria estrutura: **x = ordem no percurso em ordem**, **y = profundidade**.
São poucas linhas em `presentation/plot.py`, e é justamente o cálculo que mostra
que a árvore foi entendida — uma biblioteca de grafos esconderia essa parte.

## Testes

```bash
pytest                    # todos
pytest --cov=postoffice   # com cobertura
ruff check .              # estilo
```

`ArvoreAVL.validar()` confere as três invariantes da árvore (ordem, altura
guardada e fator de balanceamento). Se uma rotação for implementada errado,
ela acusa na hora em vez de deixar a árvore desbalanceando em silêncio.