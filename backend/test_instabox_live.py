import asyncio
from app.ai.ollama_provider import OllamaProvider
from app.core.config import settings

async def main():
    provider = OllamaProvider(
        base_url=settings.PRODUCTION_OLLAMA_BASE_URL,
        access_token=settings.OLLAMA_ACCESS_TOKEN,
    )

    try:
        print("Testing InstaBox embedding generation...")

        results = await provider.generate_embeddings_batch(
            texts=[
                "RepoMind is an AI-powered repository intelligence platform.",
                "It explains codebases using artificial intelligence."
            ]
        )

        print("Embedding count:", len(results))

        for index, result in enumerate(results):
            print(f"Embedding {index + 1} dimensions:", len(result.embedding))

        print("\nEmbedding test completed successfully.")

    except Exception as error:
        print("ERROR:", type(error).__name__, str(error))

    finally:
        await provider.close()

asyncio.run(main())
