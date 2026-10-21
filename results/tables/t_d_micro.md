### Parte D: demonstracoes isoladas (media de 3 repeticoes)

| teste          | modo            |   reps |   falha_media | metrica                                        |   tempo_ms | obs                           |   escritas |   retent_por_thread |
|:---------------|:----------------|-------:|--------------:|:-----------------------------------------------|-----------:|:------------------------------|-----------:|--------------------:|
| D1_contador    | sem_lock        |      3 |         0.000 | atualizacoes perdidas de 40000                 |      5.046 | nan                           |    nan     |             nan     |
| D1_contador    | sem_lock_janela |      3 |     35000.000 | atualizacoes perdidas de 40000                 |    390.985 | nan                           |    nan     |             nan     |
| D1_contador    | lock            |      3 |         0.000 | atualizacoes perdidas de 40000                 |   3011.296 | nan                           |    nan     |             nan     |
| D2_cache_micro | none            |      3 |       350.000 | calculos redundantes em 50 rodadas x 8 threads |    599.360 | nan                           |    nan     |             nan     |
| D2_cache_micro | lock            |      3 |       350.000 | calculos redundantes em 50 rodadas x 8 threads |    581.421 | nan                           |    nan     |             nan     |
| D2_cache_micro | singleflight    |      3 |         0.000 | calculos redundantes em 50 rodadas x 8 threads |    576.889 | nan                           |    nan     |             nan     |
| D3_log_micro   | unsafe          |      3 |      2396.667 | linhas corrompidas de 2400                     |    334.728 | nan                           |    nan     |             nan     |
| D3_log_micro   | lock            |      3 |         0.000 | linhas corrompidas de 2400                     |     64.498 | nan                           |    nan     |             nan     |
| D6_starvation  | pref_leitores   |      3 |         1.452 | espera maxima do escritor (s)                  |    nan     | escritas 1.0/5; leituras 2175 |      1.000 |             nan     |
| D6_starvation  | pref_escritor   |      3 |         0.003 | espera maxima do escritor (s)                  |    nan     | escritas 5.0/5; leituras 2157 |      5.000 |             nan     |
| D5_deadlock    | ingenuo         |      3 |         1.000 | fracao encerrada pelo pai por timeout          |   3004.795 | nan                           |    nan     |               0.000 |
| D5_deadlock    | timeout         |      3 |         0.000 | fracao encerrada pelo pai por timeout          |   1936.209 | [83, 83]                      |    nan     |              82.000 |
| D5_deadlock    | ordenado        |      3 |         0.000 | fracao encerrada pelo pai por timeout          |    266.286 | [0, 0]                        |    nan     |               0.000 |
