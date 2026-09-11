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

pytest                              # roda os testes
python3 scripts/demo_altura.py      # demonstração da Sprint 1
```

---

## Estrutura de pastas

```
correios-digital/
├── src/correios/
│   ├── estruturas/      # a árvore AVL
│   ├── seguranca/       # hash de senha e criptografia
│   ├── dominio/         # entidades: Usuario e Mensagem
│   ├── servicos/        # regras de uso (Sprint 2)
│   ├── persistencia/    # arquivo, pen drive, e-mail (Sprint 3)
│   └── apresentacao/    # telas e plotagem (Sprint 4)
├── tests/
├── scripts/
└── docs/
```

O código fica em `src/` em vez da raiz (*src layout*). O motivo prático: sem
isso, `import correios` pega a pasta do repositório mesmo quando o pacote não
foi instalado, e um teste pode passar na máquina de quem escreveu e falhar na
de outra pessoa.

### Regra de dependência

As setas apontam sempre para baixo. Nenhum módulo importa quem está acima dele.

```
apresentacao  ->  servicos  ->  dominio  ->  seguranca
                              \
                               ->  estruturas
```

- **`estruturas`** e **`seguranca`** não importam nada do projeto. São camadas
  de base, testáveis isoladamente.
- **`dominio`** conhece `seguranca` (para cifrar) mas **não** conhece
  `estruturas`: a mensagem não sabe que existe uma árvore. Quem junta os dois
  é `servicos`.
- **`persistencia`** e **`apresentacao`** ficam nas bordas, onde estão o disco,
  a rede e a tela.

Isso não é enfeite: é o que permite trocar AVL por rubro-negra, ou Tkinter por
linha de comando, sem mexer nas regras de negócio.

---

## Decisões técnicas

### Por que AVL e não uma BST comum

A chave de cada mensagem é o instante do envio. Como as mensagens chegam
sempre com horário crescente, uma árvore de busca comum insere tudo à direita
e vira uma lista encadeada.

Medido em `scripts/demo_altura.py`, com 10.000 mensagens:

| Estrutura | Altura | Comparações para achar uma mensagem |
|---|---|---|
| BST comum | 10.000 | até 10.000 |
| AVL | 14 | até 14 |

### Chave composta

A chave é a tupla `(instante, sequencia)`. Duas mensagens no mesmo segundo
desempatam pelo contador. Tuplas em Python comparam campo a campo, então a
ordenação sai de graça.

Os instantes são gravados em **UTC**. Horário local muda com fuso e horário
de verão, e isso bagunçaria a ordem do histórico.

### Autenticação e criptografia são coisas separadas

Os dois nascem da senha do usuário, mas com **salts diferentes**:

| | Para quê | Como |
|---|---|---|
| `salt_autenticacao` | conferir o login | PBKDF2-HMAC-SHA256, 600.000 iterações |
| `salt_cofre` | cifrar as mensagens | PBKDF2 → chave Fernet (AES + HMAC) |

Se os dois fossem o mesmo valor, quem roubasse o arquivo de usuários
conseguiria decifrar as mensagens. Separados, o arquivo de cadastro é inútil
para isso.

O Fernet foi escolhido porque já embute HMAC de integridade: arquivo
adulterado é detectado sozinho, sem código extra.

### Onde o texto legível existe

Só dentro de uma variável local, durante a exibição. A entidade `Mensagem`
não tem atributo com o texto puro — ela guarda apenas `conteudo_cifrado`.
Assim não há como, por descuido, gravar texto legível em disco.

A chave da sessão vive no objeto `Cofre` e é descartada no logout.

---

## Status por sprint

| Sprint | Escopo | Situação |
|---|---|---|
| 1 | Árvore AVL, cadastro, login, hash de senha | módulos prontos e testados |
| 2 | Mensagens, criptografia, histórico, busca, remoção | entidades prontas; falta a camada de serviços |
| 3 | Persistência, backup, pen drive, e-mail | a fazer |
| 4 | Plotagem, interface, documentação | a fazer |

---

## Testes

```bash
pytest                 # todos
pytest --cov=correios  # com cobertura
ruff check .           # estilo
```

Os testes da AVL incluem uma função `validar()` que confere as três
invariantes da árvore (ordem, altura guardada e fator de balanceamento).
Se uma rotação for implementada errado, ela acusa na hora em vez de deixar a
árvore desbalanceando em silêncio.
