"""Gerador de corpus sintetico e deterministico (sem dados pessoais).

Cada documento pertence a um topico e mistura termos do topico com palavras
comuns, o que basta para que a recuperacao por similaridade tenha sentido.
"""
import os
import random

TOPICOS = {
    "memoria_virtual": "paginacao pagina quadro tabela tlb falta swap enderecamento mmap residente "
                       "working set substituicao lru thrashing virtual fisica heap pilha",
    "escalonamento": "escalonador processo thread prioridade quantum preempcao fila pronto "
                     "bloqueado contexto troca cfs latencia vazao justica round robin",
    "sistemas_arquivos": "arquivo diretorio inode bloco journaling ext4 descritor open read "
                         "write fsync metadados permissao montagem superbloco extent",
    "sincronizacao": "mutex semaforo monitor condicao corrida deadlock starvation exclusao "
                     "critica espera circular trava barreira atomico futex sinal",
    "embeddings": "vetor embedding dimensao similaridade cosseno norma projecao espaco "
                  "semantico vizinho indice quantizacao produto escalar hashing",
    "rag": "recuperacao geracao contexto trecho chunk consulta documento ranking relevancia "
           "prompt resposta fonte citacao pipeline ingestao",
    "cache": "cache acerto erro remocao politica lru fifo capacidade aquecimento invalidacao "
             "localidade temporal espacial hit miss buffer",
    "armazenamento": "disco ssd nvme bloco latencia iops vazao leitura escrita sequencial "
                     "aleatoria buffer pagina dirty writeback checkpoint",
    "inferencia_llm": "modelo token prefill decodificacao kv lote contexto parametros pesos "
                      "gguf quantizado ollama servidor latencia ttft",
    "gpu_aceleracao": "gpu vram kernel cuda tensor nucleo largura banda transferencia pcie "
                      "paralelismo matriz multiplicacao precisao fp16",
}

COMUNS = ("o a os as de do da dos das em no na um uma para com por sobre entre quando "
          "sistema dados tempo uso recurso processo memoria custo medida resultado analise "
          "operacao execucao servico aplicacao experimento observacao etapa camada valor "
          "nivel maior menor alto baixo rapido lento novo atual cada mesmo outro").split()


def topicos():
    return list(TOPICOS.keys())


def termos(topico):
    return TOPICOS[topico].split()


def _frase(rng, tp):
    n = rng.randint(7, 14)
    palavras = []
    for _ in range(n):
        if rng.random() < 0.42:
            palavras.append(rng.choice(termos(tp)))
        else:
            palavras.append(rng.choice(COMUNS))
    palavras[0] = palavras[0].capitalize()
    return " ".join(palavras) + "."


def gerar_documento(rng, idx):
    tp = rng.choice(topicos())
    n_frases = rng.randint(8, 40)
    corpo = " ".join(_frase(rng, tp) for _ in range(n_frases))
    titulo = f"Documento {idx:06d} sobre {tp.replace('_', ' ')}"
    return tp, titulo, corpo


def gerar_corpus(destino, n_docs, seed=42):
    """Grava n_docs arquivos .txt em destino/docs. Retorna estatisticas."""
    rng = random.Random(seed)
    pasta = os.path.join(destino, "docs")
    os.makedirs(pasta, exist_ok=True)
    total = 0
    for i in range(n_docs):
        tp, titulo, corpo = gerar_documento(rng, i)
        texto = f"{titulo}\ntopico: {tp}\n\n{corpo}\n"
        caminho = os.path.join(pasta, f"doc_{i:06d}.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(texto)
        total += len(texto.encode("utf-8"))
    return {"n_docs": n_docs, "bytes": total, "seed": seed, "pasta": pasta}
