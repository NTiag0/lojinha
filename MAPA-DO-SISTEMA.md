# Levantamento e cobertura

Referência: sessão autorizada de https://web.kontro.com.br, examinada em 05/11/2026. A navegação no serviço original foi apenas de leitura. Foram abertos formulários, sem salvar cadastros, vendas, pagamentos ou configurações na conta original.

O levantamento se baseia nos menus, texto acessível, telas e formulários visíveis. A conta original apresentou listas vazias de produtos, clientes, pedidos e fornecedores. Algumas telas retornaram apenas o estado inicial de carregamento durante a navegação, e funções PRO estavam bloqueadas. Por isso, a versão local reproduz a finalidade dos módulos e implementa regras próprias; não afirma equivalência completa com comportamentos internos não observados.

## Módulos operacionais

| Referência original | Implementação local | Cobertura |
|---|---|---|
| `/home` | `#home` | Ações rápidas, cadastros, indicadores, aviso de backup, atalho de caixa. |
| `/order` | `#order` | Busca, código de barras, categorias, itens, variações e fechamento. Uma tela de seleção e formulário de fechamento; não duplica os modos Clássico/Balcão do original. |
| `/order/manual` | `#manual` | Venda sem produto; título, valor, descontos, taxas, entrega, cliente, vendedor e observações. |
| `/order/list` | `#orders` | Lista, Kanban, status, detalhes, recebimentos e cancelamento com estoque/estorno. |
| `/order/quotes` | `#quotes` | Orçamento sem baixa de estoque; conversão em venda e cancelamento. |
| `/tables-settings` | `#tables` | Mesa ou comanda, atendimento aberto, inclusão de itens e liberação por status. |
| `/cash-session` | `#cash` | Troco inicial, abertura, dinheiro esperado, suprimento/sangria via lançamentos, conferência e diferença. Apenas um caixa aberto por vez. |
| `/financial` | `#financial` | Entradas/despesas, pago/pendente, categoria, fornecedor, recorrência diária/semanal/mensal e até 60 ocorrências. |
| `/debts` | `#debts` | Saldo de pedidos, entradas a receber, despesas a pagar, recebimento e mensagem de cobrança para copiar. |
| `/product-stock` | `#stock` | Quantidade, mínimo, custo e venda em estoque, ajuste de entrada/saída e variação. |
| `/supplier-orders` | `#purchases` | Compra com vários itens, fornecedor, recebimento, entrada em estoque, conta a pagar e pagamento. |
| `/products/labels` | `#labels` | Seleção e quantidade, preço, Code 128, grade de 2/3/4 colunas e prévia de impressão. |
| `/dashboard` | `#dashboard` | Evolução diária, vendas, ticket médio, margem bruta, rankings e métodos de pagamento. |

## Cadastros

| Referência original | Implementação local | Cobertura |
|---|---|---|
| `/products` | `#products` | Produto/serviço, foto local, descrição, código, custo, preço, cálculo de lucro, categoria, fornecedor, oferta, atacado por quantidade, estoque fracionado, variações, visibilidade e mensagem no recibo. |
| `/clients` | `#clients` | Nome, documento, celular, e-mail, nascimento, observação, endereço, campos extras e aniversariantes do mês. |
| `/suppliers` | `#suppliers` | Nome, documento, celular e observação. |
| `/product-categories` | `#categories` | Cadastro, edição, busca, ordenação alfabética e arquivamento. |
| `/variation-templates` | `#variations` | Padrões com nomes separados por vírgula; aplicação ao criar produtos. |
| `/financial-category` | `#financialCategories` | Título e tipo de categoria. |
| `/delivery-options` | `#deliveries` | Formas e valores de entrega manuais. |
| `/payment-options` | `#paymentMethods` | Métodos ativos, taxa estimada e instruções. Recebimentos são confirmados manualmente. |
| `/users` | `#users` | Vendedores e comissão estimada. Não cria usuários autenticados. |

## Relatórios

Todos os relatórios locais possuem tabela, busca, exportação CSV e impressão/Salvar como PDF. Filtros de data usam a data do movimento ou pedido. Não há geração nativa de arquivos XLSX nem o conjunto completo de filtros do original.

| Referência original | Rota local |
|---|---|
| `/reports/order-summary` | `#report-summary` |
| `/reports/order` | `#report-orders` |
| `/reports/orders-with-pending-payments` | `#report-debts` |
| `/reports/product-stock` | `#report-stock` |
| `/reports/product-stock-movement` | `#report-movements` |
| `/reports/financial` | `#report-financial` |
| `/reports/payments-by-payment-method` | `#report-methods` |
| `/reports/client` | `#report-clients` |
| `/reports/seller` | `#report-sellers` |
| `/reports/coupon` | `#report-coupons` |
| `/reports/product` | `#report-products` |

Os relatórios de estoque e os rankings que não foram inspecionados em detalhe foram reconstruídos a partir da finalidade informada no menu. A posição de estoque é sempre atual; datas filtram movimentos, não reconstroem um saldo histórico.

## Catálogo e configuração

| Referência original | Rota local | Cobertura |
|---|---|---|
| `/store-config` | `#store`, `#catalog` | Nome, foto, mensagem, cor configurável, formato grade/lista, visibilidade, estoque esgotado, mínimo e texto de horário. Catálogo local junto à gestão. |
| `/store-config/banners` | `#banners` | Imagens locais, ordem e situação. Banners aparecem em sequência; não há carrossel automático. |
| `/store-config/coupons` | `#coupons` | Percentual/fixo, mínimo, validade e limite de usos. Formulário PRO original bloqueado; regras locais. |
| `/store-config/payment-type-discounts` | `#paymentDiscounts` | Desconto percentual pelo método principal selecionado no fechamento. Regra local, inclusive para pagamentos divididos. |
| `/product-catalog` | `#catalog-pdf` | Visualização de catálogo para impressão/Salvar como PDF. Sem todas as opções avançadas do original. |
| `/change-name`, `/change-company-name` | `#settings` | Nome do responsável, negócio e preferências. |
| `/company-address` | `#address` | Endereço e opções de exibição. |
| `/customize-receipt` | `#receipt` | Identificação, logo, mensagem, endereço e assinaturas. |
| `/customize-charge` | `#charge` | Modelo com cliente, pedido e saldo. Copiar texto, sem envio automático. |
| `/printers` | `#printers` | Largura de recibo 58/80 mm; impressão pelo navegador. |
| `/order-custom-fields` | `#orderFields` | Campos de texto, obrigatoriedade e impressão. |
| `/client-custom-fields` | `#clientFields` | Campos de texto, obrigatoriedade e impressão. |
| `/cash-session-settings` | `#cash-settings` | Nome do caixa e lembrete de abertura. |
| Backup próprio | `#backup` | Exportação/restauração de dados e preservação do estado anterior. |

## Dependências e diferenças pendentes

- Nota fiscal (`/fiscal`): a conta apresentou uma oferta de ativação, com descrição do serviço. A aplicação própria não emite documento fiscal, não faz análise de CNPJ nem opera certificado digital.
- Gateways de pagamento, SuperFrete, frete por distância, geolocalização de clientes, notificações push e catálogo público não estão integrados.
- Login, alteração de senha/celular e exclusão de conta do Kontro não foram copiados. A aplicação é de uso local e independente dessa conta.
- Combos com componentes, preço sob consulta, múltiplas fotos por produto, catálogo atacadista separado, ordenação manual de catálogo e importação em massa do Kontro não estão implementados.
- Não há equivalência garantida em arredondamentos, parcelamentos, regras de cupom, permissões, agrupamentos avançados, cálculo de comissões ou regras fiscais.
- Reserva de estoque no catálogo exige validação adicional para checkout independente. A tela local de catálogo verifica a disponibilidade inicial, mas o fechamento atual é feito na gestão, usando o estoque total disponível.
- A identidade da aplicação pode ser personalizada com a logo, nome e cores em Negócio e Preferências; a configuração inicial do catálogo acompanha a cor principal.
- Nenhuma credencial foi copiada, armazenada no projeto ou extraída do navegador. Nenhum dado foi sincronizado automaticamente com o Kontro.

## Validação realizada

- 19 testes automatizados de regras e HTTP, em bancos temporários.
- 49 rotas locais navegadas com leitura dos títulos, sem erros no console nessa rodada.
- Cadastro de produto, venda parcial, venda em duas formas, visualização de etiqueta e atendimento de mesa com inclusão posterior de consumo exercitados no navegador, em base separada.
- Inspeção visual da tela inicial e das etiquetas. Impressão física, scanners e serviços externos não foram testados.

## Atualização de menus e despesas operacionais

- Cadastros, Relatórios, Configurações do catálogo e Configurações agora expandem e recolhem, com a escolha mantida no navegador.
- O lançamento de despesas permanece em Financeiro → Despesa, sem menu ou tela separada de Despesas.
- Despesas operacionais contém sete subcategorias: Frete de mercadoria, Aluguel, Conta de água, Conta de energia, Conta de internet, Despesa viagem — Alimentação e Despesa viagem — Gasolina.
- A categoria e a subcategoria aparecem no extrato financeiro e em sua exportação. A reorganização preserva os valores, pagamentos e referências dos lançamentos já existentes.
- Verificação atual: 26 testes automatizados aprovados (23 de negócio/HTTP e 3 de cores/contraste), incluindo migração das categorias sem perda de lançamentos. Os grupos de menu e a seleção das subcategorias também foram conferidos no navegador em uma base separada.

## Identidade visual da loja

Negócio e Preferências possui envio/remoção de logo, nome do negócio, sugestão automática de duas cores a partir da imagem, escolha manual de cores e prévia antes de salvar. A identidade é aplicada ao cabeçalho, favicon, rodapé, menus, botões, atalhos e gráficos. Logo e nome são compartilhados com catálogo e recibos; a exibição no recibo continua respeitando sua opção de mostrar logo. A extração ocorre localmente no navegador. Foram conferidos o envio de PNG, sugestão automática, persistência após recarregar e alteração manual sem sobrescrita pela sugestão automática.
