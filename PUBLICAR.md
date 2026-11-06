# Publicar a Lojinha no Render

A aplicação pode rodar online sem depender do computador. O modo local continua disponível e seus dados locais não são enviados ao GitHub.

## Configuração pronta

`render.yaml` define um serviço Python gratuito, com uma única instância e verificação de saúde em `/healthz`. O serviço usa um banco PostgreSQL externo, como o Neon Free. O app pode hibernar após um período sem acesso, e o primeiro acesso seguinte pode demorar. Confira as cotas de uso dos planos gratuitos.

O serviço usa `PORT` e aceita conexões no endereço de hospedagem. A origem pública é lida de `RENDER_EXTERNAL_HOSTNAME`; para domínio próprio, configure `LOJINHA_PUBLIC_URL` com a origem HTTPS exata, por exemplo `https://loja.exemplo.com`.

## Acesso protegido

O modo de publicação exige usuário e hash da senha antes de iniciar. Não há cadastro público. Cada sessão expira após 12 horas. A aplicação usa cookies protegidos, limite de tentativas de entrada e bloqueio de requisições de outros sites. A troca do hash da senha revoga as sessões anteriores.

Execute `python tools/prepare_access.py` para gerar o acesso inicial. O script cria:

- `data/acesso-online.txt`: usuário e senha para o responsável.
- `data/render-access.json`: valores privados para configurar o serviço no Render. Contém o usuário e somente o hash da senha.

Esses arquivos ficam fora do Git. Nenhuma senha ou banco de dados deve ser enviado ao repositório.

No Render, configure `LOJINHA_ADMIN_USER` e `LOJINHA_ADMIN_PASSWORD_HASH` com os valores do arquivo privado. Configure `LOJINHA_DATABASE_URL` com a conexão PostgreSQL do projeto Neon e `LOJINHA_REQUIRE_POSTGRES=1`. Mantenha a conexão e o hash nos segredos do serviço. A URL pública só será confirmada após o serviço terminar a implantação e passar na verificação de saúde.

## Dados

Na hospedagem, o banco PostgreSQL mantém os cadastros, fotos, configurações e sessões entre reinícios e atualizações. O banco online é independente do SQLite local. A aplicação online se recusa a iniciar se a conexão com o banco não for configurada, para evitar gravações em um disco temporário.

Depois de entrar na aplicação online, um backup local pode ser restaurado pela área Cópias de Segurança. A publicação inicial não envia automaticamente os dados locais. Sessões e credenciais não estão incluídas nos backups de negócio.

## Atualizações

O código fica no repositório da aplicação no GitHub. Os dados e credenciais permanecem fora do repositório, inclusive se ele estiver público. Com implantação automática ativa, os envios para a branch configurada iniciam novas implantações. Mantenha a mesma conexão PostgreSQL para preservar os dados entre versões.

O modelo atual foi preparado para um responsável e uma única instância. Para acesso individual de vários usuários, será necessário implementar contas e permissões.

## Verificar antes de publicar

`python -m unittest discover -s tests -v`

`node --test tests/branding.test.mjs`

Os testes incluem bloqueio de leitura e gravação sem login, entrada e saída, expiração, limitação de tentativas, revogação de sessões após troca da senha, proteção de origem, preservação dos dados e ausência de credenciais nos backups.
