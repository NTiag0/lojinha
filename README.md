# Lojinha local

Aplicação própria para gestão de uma loja, reconstruída a partir dos módulos e fluxos visíveis na sessão autorizada do Kontro em 5 de novembro de 2026. A interface usa a marca Lojinha e o código é independente.

## Abrir

1. Dê dois cliques em **iniciar.bat** nesta pasta.
2. O navegador abrirá em **http://127.0.0.1:8765**.
3. Mantenha a janela do servidor aberta enquanto usa a aplicação. Para encerrar, feche essa janela.

Requer Python 3.10 ou superior, já disponível no computador usado para criar o projeto. Não precisa instalar pacotes, ter internet ou usar uma conta do Kontro.

Alternativa pelo terminal: `python server.py --open`. Para outra porta: `python server.py --port 8770 --open`.

## Primeiros passos

- Em **Negócio e Preferências**, informe o nome do negócio e seus dados.
- Cadastre categorias, fornecedores e produtos. Informe custo, preço e quantidade inicial.
- Para variações, use uma linha por opção, como `Azul / M | 5`. Padrões de variação podem preencher os nomes com saldo inicial zero.
- Depois de criado um produto, altere as quantidades em **Estoque → Movimentar**. As variações são definidas no cadastro inicial.
- Abra o caixa se desejar conferir o dinheiro da gaveta.
- Em **Registrar Venda de Produtos**, selecione os itens e feche a venda. Há opções de desconto, taxa, entrega, cupom, cliente, vendedor, prazo e pagamento parcial ou dividido.
- Em **Pagamentos Pendentes**, registre recebimentos posteriores. As formas adicionais de pagamento são registradas separadamente no financeiro.
- Em **Mesas e Comandas**, ative o atendimento desejado, cadastre as mesas e inicie o atendimento. No pedido aberto é possível adicionar itens. Para liberar a mesa, altere o pedido para Concluído após o atendimento.

## Menus e despesas operacionais

Cadastros, Relatórios, Configurações do catálogo e Configurações podem ser expandidos ou recolhidos pelo cabeçalho com os sinais + e −. O navegador mantém sua preferência ao trocar de tela ou recarregar.

Para registrar uma despesa, use **Financeiro → Despesa**. Ao escolher **Despesas operacionais**, o campo **Subcategoria** oferece frete de mercadoria, aluguel, conta de água, conta de energia, conta de internet, despesa viagem — alimentação e despesa viagem — gasolina. O tipo escolhido aparece no extrato e no relatório financeiro. Os gastos de viagem também podem receber um destino opcional. Não há uma área separada de Despesas.

## Logo, nome e cores

Abra **Configurações → Negócio e Preferências** para trocar o nome do negócio e enviar a logo (PNG, JPG ou WebP de até 2 MB). A prévia mostra a identidade antes de salvar. Ative **Sugerir cores automaticamente a partir da logo** ou use **Usar cores da logo** para extrair duas cores principais da imagem. Também é possível ajustar **Cor principal** e **Cor de destaque** manualmente; ao fazer isso, a sugestão automática é desativada para preservar sua escolha.

Após salvar, o nome e a logo aparecem no cabeçalho, no catálogo e nos recibos. As cores personalizam os botões, menus, atalhos e gráficos da aplicação, e são usadas como cor inicial do catálogo. Logo e cores ficam nos dados locais e no backup. A leitura das cores acontece no próprio navegador, sem enviar a imagem a um serviço externo. Logos monocromáticas recebem uma sugestão neutra, que pode ser ajustada manualmente.

## Dados e cópias de segurança

O banco fica em `data/lojinha.sqlite3`. Os cadastros e movimentos persistem ao fechar o navegador ou reiniciar o computador.

Use **Cópias de Segurança → Baixar cópia de segurança**. Guarde o arquivo em outro local para proteger os dados contra perda do computador. A restauração aceita arquivos desta aplicação e substitui o conjunto atual. Antes de restaurar, a aplicação preserva os dados anteriores em `data/backups` e em um histórico no banco.

Não copie somente o arquivo SQLite enquanto o servidor estiver aberto: ele usa arquivos auxiliares de transação. Para copiar a pasta manualmente, feche o servidor primeiro; para copiar durante o uso, prefira a exportação da aplicação.

Arquivar um cadastro o remove das seleções, preservando suas referências no histórico. Cancelar uma venda devolve o estoque e registra estornos financeiros. O cancelamento registra o estorno no sistema; a devolução real de dinheiro ou cartão deve ser efetuada pelo responsável.

## Relatórios e impressão

Há relatórios de pedidos, pendências, posição e movimentação de estoque, financeiro, métodos de pagamento, produtos, clientes, vendedores e cupons. As tabelas podem ser exportadas em CSV, compatível com Excel.

**Imprimir / PDF** abre a impressão do navegador. Escolha **Salvar como PDF** para gerar um arquivo. Recibos são comprovantes não fiscais. Etiquetas usam Code 128 para códigos ASCII de até 40 caracteres. Os modelos de etiquetas são grades genéricas; confira a escala e a folha antes de imprimir em adesivos. A geração visual foi conferida, mas o alinhamento em impressora física e a leitura por scanner não foram ensaiados.

O lucro exibido nos gráficos é margem bruta estimada: total de vendas menos o custo dos itens. Não é uma apuração contábil de lucro líquido. O relatório por método lista taxas de operadora estimadas separadamente. O financeiro registra os valores brutos; as taxas efetivamente descontadas podem ser registradas como despesas.

## Cobertura e limites

Consulte **MAPA-DO-SISTEMA.md** para a correspondência entre os módulos observados e a versão local.

Esta versão contém 49 rotas locais e os fluxos centrais implementados. Não é uma réplica integral certificada do Kontro: recursos pagos bloqueados, regras de bastidor e integrações externas não puderam ser reproduzidos ou validados integralmente.

- Emissão fiscal, cobrança automática, gateways de pagamento, frete automático, domínio público e notificações em segundo plano não estão conectados.
- O catálogo é uma visualização local, dentro da aplicação de gestão, sem área pública ou checkout independente.
- Vendedores são cadastros de acompanhamento, sem acesso individual ou controle de permissões. A versão local usa apenas conexões locais. A hospedagem possui login do responsável, com configuração descrita em PUBLICAR.md.
- Não houve migração automática de dados ou credenciais da conta original.
- Combos, preço sob consulta, catálogo atacadista separado, personalização completa de relatórios e integração de impressoras não foram implementados.
- Recursos adicionais, como agrupamentos avançados, impressão fiscal e geolocalização de clientes, permanecem fora desta versão.

## Verificação

`python -m unittest discover -s tests -v`

Os testes de extração de cores e contraste podem ser executados com `node --test tests/branding.test.mjs`. O comando `npm test` executa as duas verificações.

Os testes usam bancos temporários e cobrem integridade de estoque, pagamentos parciais e divididos, cancelamentos, caixa, orçamentos, compras, variações, recorrência, backup/restauração e as rotas HTTP. A interface também foi navegada no navegador integrado, em uma base de teste separada.

## Estrutura

- `server.py`: servidor HTTP local, regras de negócio e SQLite.
- `public/`: telas, estilos, identidade visual, ícones e impressão, sem dependências externas.
- `tests/`: testes com dados temporários.
- `iniciar.bat`: abertura da aplicação no Windows.

Para a versão hospedada, consulte PUBLICAR.md. O modo de publicação exige origem HTTPS, credenciais do responsável e armazenamento persistente.

A versão hospedada inclui login e saída, sessão com expiração, cookies protegidos e limite de tentativas de acesso. Os dados locais não são publicados junto com o código.
