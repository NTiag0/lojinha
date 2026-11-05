"""Prepare private deployment credentials without printing them or using Git."""
import json
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from security import password_hash

root=Path(__file__).resolve().parents[1]
private=root/'data';private.mkdir(exist_ok=True)
config=private/'render-access.json'
readable=private/'acesso-online.txt'
if config.exists() or readable.exists():
    print('Os arquivos de acesso já existem. Nenhuma senha foi substituída.')
else:
    password=secrets.token_urlsafe(20)
    config.write_text(json.dumps({'LOJINHA_ADMIN_USER':'tiago','LOJINHA_ADMIN_PASSWORD_HASH':password_hash(password)},indent=2),encoding='utf-8')
    readable.write_text('Acesso da Lojinha online\n\nUsuário: tiago\nSenha: '+password+'\n\nGuarde em um local privado. Não envie este arquivo ao GitHub.\nO endereço será informado após a publicação.\n',encoding='utf-8')
    print('Acesso preparado em data/acesso-online.txt. Configuração privada em data/render-access.json.')
