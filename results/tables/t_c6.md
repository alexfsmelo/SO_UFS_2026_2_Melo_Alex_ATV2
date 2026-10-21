### C6: falhas controladas

| caso                | variante                                  | resultado                                                                                                      |   codigo |   reps |   duracao_s |
|:--------------------|:------------------------------------------|:---------------------------------------------------------------------------------------------------------------|---------:|-------:|------------:|
| arquivo_ausente     | 5 arquivos inexistentes                   | 500 docs ingeridos; 5 falhas registradas no log                                                                |        0 |      3 |      nan    |
| indice_indisponivel | ausente                                   | {"erro": "indice_indisponivel", "msg": "arquivo do indice ausente: index/S_falha/vectors.f32"}                 |        2 |      3 |        0.13 |
| indice_indisponivel | truncado                                  | {"erro": "indice_indisponivel", "msg": "vectors.f32 inconsistente: 1380352 bytes, esperado 2760704 (arquivo tr |        2 |      3 |        0.13 |
| indice_indisponivel | reconstrucao                              | {"erro": "indice_indisponivel", "msg": "arquivo do indice ausente: index/S_falha/vectors.f32"}                 |        0 |      3 |        0.92 |
| fila_saturada       | cap=2.0, timeout=0.005s, retentativas=0.0 | descartadas 75.0/80; rejeicoes 75.0; espera media 94 ms                                                        |        0 |      3 |      nan    |
| fila_saturada       | cap=2.0, timeout=0.005s, retentativas=3.0 | descartadas 64.0/80; rejeicoes 273.7; espera media 133 ms                                                      |        0 |      3 |      nan    |
| fila_saturada       | cap=64.0, timeout=30.0s, retentativas=0.0 | descartadas 0.0/80; rejeicoes 0.0; espera media 2561 ms                                                        |        0 |      3 |      nan    |
| limite_memoria      | read, limite 192 MB sem swap              | 0 concluidas, 3 mortas por OOM                                                                                 |       -9 |      3 |      nan    |
| limite_memoria      | mmap, limite 192 MB sem swap              | 3 concluidas, 0 mortas por OOM                                                                                 |        0 |      3 |      nan    |
| servico_externo     | falha=20%, retentativas=0.0               | erros 22.3/100; retentativas 0.0; servico medio 66 ms                                                          |        0 |      3 |      nan    |
| servico_externo     | falha=20%, retentativas=2.0               | erros 1.0/100; retentativas 25.0; servico medio 84 ms                                                          |        0 |      3 |      nan    |
| servico_externo     | falha=50%, retentativas=0.0               | erros 48.7/100; retentativas 0.0; servico medio 66 ms                                                          |        0 |      3 |      nan    |
| servico_externo     | falha=50%, retentativas=2.0               | erros 12.3/100; retentativas 49.0; servico medio 105 ms                                                        |        0 |      3 |      nan    |
| ollama_indisponivel | backend ollama, porta sem servico         | erros 10/10, processo nao caiu                                                                                 |        0 |      3 |      nan    |
