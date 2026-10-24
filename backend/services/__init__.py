"""CYPHEX — multi-service (microservice) static discovery.

Phase 1 of the microservice VAPT plan: build a ServiceGraph from source
(inbound routes + outbound calls per service, cross-service edges resolved
by name), with no live traffic and no change to how a single-service repo
scans. Phases 2 (feed the graph into the DeepAgents swarm) and 3 (deploy all
services on one network and chain live findings across them) build on this
but are not implemented yet.
"""
