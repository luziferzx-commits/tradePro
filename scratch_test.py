import time

def test():
    start = time.time()
    for i in range(10_000_000):
        # same logic
        labels = {"worker": str(i%10)}
        label_str = ",".join([f"{k}={v}" for k, v in sorted(labels.items())])
        s = f"stress_counter{{{label_str}}}"
    end = time.time()
    print("Time:", end - start)

if __name__ == "__main__":
    test()
