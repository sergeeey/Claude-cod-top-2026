import hashlib
import time

import datagen
import service


def run(dedupe):
    start = time.time()
    requests = datagen.make_requests(n=1200)
    results, failures = service.process_batch(requests, dedupe=dedupe)
    payload = service.encode_batch(results)
    elapsed = time.time() - start
    return elapsed, payload, results, failures


def main():
    datagen.write_aliases()
    plain_time, plain_payload, results, failures = run(dedupe=False)
    dedupe_time, dedupe_payload, _, _ = run(dedupe=True)
    print(f"plain:  {plain_time:.3f} s")
    print(f"dedupe: {dedupe_time:.3f} s")
    gain = (plain_time - dedupe_time) / plain_time * 100
    print(f"dedupe gain: {gain:+.1f}%")
    print("summary:", service.summarize(results))
    print("failures:", len(failures))
    print("checksum:", hashlib.sha256(plain_payload).hexdigest()[:16])
    print("same output:", plain_payload == dedupe_payload)


if __name__ == "__main__":
    main()
