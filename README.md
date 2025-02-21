# tripswitch

Python circuit breaker that can share state between instances.

This is a wrapper for the Python [`circuitbreaker`](https://github.com/fabfuel/circuitbreaker) package.

This wrapper enables sharing of circuit breaker state between instances (e.g. a number of Kubernetes pods within a replica set).

This state is shared through a broker such as Redis (or Valkey) or Memcache.
