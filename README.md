# sysopt-buildcache

Measure how much of a Docker/BuildKit build actually came from cache, and point
at the Dockerfile steps that destroy it.

CI is slow because the cache misses, not because the compiler is slow. This tool
reads a `--progress=plain` build log and reports the cache hit rate, the time
spent executing steps, and the specific anti-patterns behind the misses.

```text
$ sysopt-buildcache examples/build.log --slow-step-s 10
build: 9 steps, 3 cached, 6 executed, 0 failed
cache hit rate: 33.3% (target 50%)
executed time: 38.1s

findings:
  error   download-execute     #8    [7/9] RUN curl -sSL https://get.example.com/install.sh | sh
          a network download is piped straight into a shell
          -> download, verify a checksum, then execute a pinned artifact
  warning low-cache-hit        -     build cache
          only 33.3% of steps came from cache (target 50%)
          -> copy lockfiles and install dependencies before copying the rest of the build context
  warning cache-busting-copy   #5    [4/9] COPY . .
          the whole build context is copied before dependency installation, so every source edit invalidates the dependency cache
          -> COPY the lockfile(s) first, RUN the install, then COPY the source
  warning add-url              #9    [8/9] ADD https://example.com/assets.tar.gz /app/assets/
          ADD from a URL is not cacheable and cannot be verified
          -> use RUN curl with a checksum, or vendor the artifact
  info    slow-step            #6    [5/9] RUN npm ci
          step took 18.4s
          -> move it earlier so it is cached more often, or split it

slowest executed steps:
     18.4s  #6 [5/9] RUN npm ci
      9.8s  #7 [6/9] RUN npm run build
      6.2s  #10 [9/9] RUN npm test
```

## Install

```bash
pip install -e .
sysopt-buildcache build.log

# or without installing
PYTHONPATH=src python -m sysopt_buildcache.cli build.log
```

## Capturing a log

```bash
docker build --progress=plain -t myapp . 2>&1 | tee build.log
sysopt-buildcache build.log
```

BuildKit's step lines (`#5 [2/9] RUN npm ci`, `#5 CACHED`, `#5 DONE 18.4s`)
are what the parser understands. `[internal]` steps are ignored.

## Rules

| Rule | Severity | What it catches |
| --- | --- | --- |
| `low-cache-hit` | warning | cache hit rate below `--min-hit-rate` (default 50%) |
| `cache-busting-copy` | warning | `COPY .` before a dependency install step |
| `unpinned-apt` | warning | `apt-get update` without removing `/var/lib/apt/lists` |
| `download-execute` | error | `curl`/`wget` piped directly into `sh` or `bash` |
| `add-url` | warning | `ADD http(s)://...`, which is never cached |
| `slow-step` | info | an executed step longer than `--slow-step-s` (default 30s) |

## Usage

```bash
# text report
sysopt-buildcache build.log

# machine-readable
sysopt-buildcache build.log --format json

# stricter cache target; fail CI when it is missed
sysopt-buildcache build.log --min-hit-rate 0.8 --fail-on-low-cache

# flag anything over 10 seconds
sysopt-buildcache build.log --slow-step-s 10

# only show errors
sysopt-buildcache build.log --min-severity error
```

Exit codes: `0` success, `1` cache rate below the target with
`--fail-on-low-cache`, `2` unreadable or unrecognised log.

## What the numbers mean

- **cache hit rate** = cached steps / (cached + executed). Failed steps count as
  executed.
- **executed time** = sum of the durations BuildKit reports for executed steps.
  Cached steps contribute zero.
- The report is about *step count*, not wall-clock accounting. A 30s cached step
  still counts as one cached step; use the slowest-steps list for time-weighted
  decisions.

## Design notes

- Parsing is offline and read-only; it never talks to the Docker daemon.
- The anti-pattern checks are intentionally conservative. They flag patterns
  that are almost always wrong in a Dockerfile, not everything that could be
  slow.
- `cache-busting-copy` only fires when a broad `COPY .` is followed by a
  dependency install in the same build, which is the canonical ordering bug.

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

## License

MIT