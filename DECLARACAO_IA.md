# Declaração de Uso de IA Generativa (AV2)

## Ferramenta e modelo

Claude (Anthropic), modelo Claude Opus 5.5, usado no aplicativo Claude em modo de agente, com acesso a uma máquina virtual Linux própria do serviço, onde o código foi escrito e os experimentos foram executados sob a orientação do discente.

## Finalidade de cada uso

* Proposta da arquitetura do GenResearch-Servidor a partir do enunciado da Atividade 2 e implementação do pacote `genresearch/` (ingestão, índice com `read()`/`mmap()`, buffer limitado com semáforos, cache compartilhado, log, gerador simulado e integração opcional com Ollama).
* Escrita dos scripts de experimento (`experiments/`), do script de evidências e do script de análise que gera tabelas e gráficos.
* Execução dos experimentos C1 a C6 e da Parte D na VM Linux descrita em `results/evidence/ambiente.txt` (KVM, Ubuntu 24.04.5, 2 vCPUs, 7,8 GiB).
* Redação inicial do relatório, dos slides, do README e do roteiro do vídeo, a partir dos dados brutos gerados pelos scripts.

## Prompts relevantes

1. "Essa é a atividade 2. Preciso começar, finalizar e entregar essa atividade até hoje." (com o PDF do enunciado anexado)
2. PREENCHER: demais pedidos de ajuste feitos durante a revisão.

## Sugestões aproveitadas, corrigidas ou rejeitadas

**Aproveitadas:** recorte experimental (corpus sintético S/M/L, vetores por *feature hashing*, geração simulada calibrada como espera de E/S), arquitetura de produtores e consumidores com semáforos `empty`/`full` e mutex, uso de cgroup para limitar memória com segurança, estrutura do relatório.

**Corrigidas durante o próprio trabalho:**

* A primeira versão da carga "limitada por CPU" queimava CPU até atingir um tempo de parede (40 ms). Com o GIL, uma thread desescalonada continuava "contando tempo", e o C3 mostrou um ganho de vazão falso de 1 para 4 trabalhadores. O erro foi identificado na leitura da tabela de C3 e corrigido para uma quantidade fixa de trabalho calibrada no início do processo; o C3 foi executado de novo.
* Uma versão intermediária do produtor gravava o instante de enfileiramento no dicionário da requisição **depois** do `put()`, quando um trabalhador já podia estar lendo o mesmo objeto (condição de corrida no próprio instrumento de medida). O campo foi removido; a espera passou a ser medida desde a criação da requisição.
* Na primeira execução do C5c, o mmap sob limite de cgroup não mostrou nenhum efeito (zero faltas maiores mesmo com 64 MB). A causa: no cgroup v1, a página de arquivo é cobrada do cgroup que a trouxe para a memória, e o arquivo já estava no cache de páginas, cobrado do cgroup pai. O experimento passou a descartar o cache antes de cada execução e foi refeito; os números do relatório são os da segunda execução.

**Rejeitadas:** PREENCHER (por exemplo, trechos de texto que o discente reescreveu).

## Erros e limitações conhecidos

* Os embeddings são simulados por *hashing*; não representam qualidade semântica de um modelo real.
* A geração é simulada por padrão; o modo Ollama está implementado, mas não foi usado nas medições do relatório.
* Os números do relatório vêm da VM descrita acima, não do notebook do discente (AMD Ryzen 7 7735HS, WSL2). PREENCHER: resultado da reexecução de conferência no WSL2 (`REPS=1 ./run_all.sh rapido`).

## Verificação

* Todos os valores das tabelas e gráficos são gerados por `experiments/analise.py` diretamente dos CSVs em `results/raw/`; nenhum número foi digitado à mão.
* PREENCHER: conferência feita pelo discente (leitura do código, reexecução, inspeção dos gráficos e do PDF).
