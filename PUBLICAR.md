# Publicar a Lojinha no Render

A aplicação pode rodar online sem depender do computador. O modo local continua disponível e seus dados locais não são enviados ao GitHub.

## Configuração pronta

`render.yaml` define um serviço Python, com uma única instância, um disco persistente de 1 GB e verificação de saúde em `/healthz`. O plano especificado é pago. A criação/aplicação deve ser aprovada após conferir o orçamento no Render.

O serviço usa `PORT` e aceita conexões no endereço de hospedagem. A origem pública é lida de `RENDER_EXTERNAL_HOSTNAME`; para domínio próprio, configure `LOJINHA_PUBLIC_URL` com a origem HTTPS exata, por exemplo `https://loja.exemplo.com`.

## Acesso protegido

O modo de publicação exige usuário e hash da senha antes de iniciar. Não há cadastro público. Cada sessão expira após 12 horas. A aplicação usa cookies protegidos, limite de tentativas de entrada e bloqueio de requisições de outros sites. A troca do hash da senha revoga as sessões anteriores.

Execute `python tools/prepare_access.py` para gerar o acesso inicial. O script cria:

- `data/acesso-online.txt`: usuário e senha para o responsável.
- `data/render-access.json`: valores privados para configurar o serviço no Render. Contém o usuário e somente o hash da senha.

Esses arquivos ficam fora do Git. Nenhuma senha ou banco de dados deve ser enviado ao repositório.

No Render, configure `LOJINHA_ADMIN_USER` e `LOJINHA_ADMIN_PASSWORD_HASH` com os valores do arquivo privado. O Blueprint exige que o hash seja fornecido antes de aplicar a publicação. A URL pública só será confirmada após o serviço terminar a implantação e passar na verificação de saúde.

## Dados

O disco persistente é montado em `/var/data/lojinha`. Ele mantém o SQLite, as fotos guardadas nos cadastros e as configurações entre reinícios e atualizações. O banco online é independente do banco local.

Depois de entrar na aplicação online, um backup local pode ser restaurado pela área Cópias de Segurança. A publicação inicial não envia automaticamente os dados locais. Sessões e credenciais não estão incluídas nos backups de negócio.

## Atualizações

O código fica no repositório da aplicação no GitHub. Os dados e credenciais permanecem fora do repositório, inclusive se ele estiver público. Com o Blueprint aprovado e sincronização automática ativa, os envios para a branch configurada iniciam novas implantações. O disco não deve ser removido ou substituído durante as atualizações.

O modelo atual foi preparado para um responsável e uma única instância. Não aumente o número de instâncias usando o mesmo arquivo SQLite. Para vários usuários ou escala horizontal, será necessário migrar o banco e implementar as permissões correspondentes.

## Verificar antes de publicar

`python -m unittest discover -s tests -v`

`node --test tests/branding.test.mjs`

Os testes incluem bloqueio de leitura e gravação sem login, entrada e saída, expiração, limitação de tentativas, revogação de sessões após troca da senha, proteção de origem, preservação dos dados e ausência de credenciais nos backups.
