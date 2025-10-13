from transformers import pipeline

def main():
    # This will download the model first time (internet required)
    generator = pipeline("text-generation", model="distilgpt2")
    out = generator("Plan a one-day trip to Paris:", max_length=50)
    print(out)

if __name__ == "__main__":
    main()