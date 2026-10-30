# Contributing to PeerAgent

Thank you for your interest in contributing to **PeerAgent**! We welcome contributions, bug reports, and suggestions from developers building multi-agent workflows.

---

## 🧭 Core Principles

Before opening a pull request, please keep our core architectural tenets in mind:

1. **Zero External Runtime Dependencies**:  
   The core `peer` CLI is intentionally designed to run on the **pure Python 3.10+ standard library**. Do not introduce external `pip` packages (like `requests`, `pydantic`, `typer`, etc.) into the runtime core.
2. **Defensive Safety by Default**:  
   Review and analysis tasks must remain strictly read-only (`--sandbox read-only` on Codex, write tools stripped on Claude). Write actions must remain gated behind explicit human quotes and snapshot diffs.
3. **Anti-Recursion Taint Tracking**:  
   Always propagate `PEER_DEPTH` to ensure agents cannot inadvertently form infinite loop deadlocks.
4. **Subscription-Native CLI Focus**:  
   PeerAgent connects locally authenticated CLIs rather than requiring separate API tokens.

---

## 🛠️ Local Development & Testing

### Prerequisites
- Python 3.10 or higher.
- Official `claude` and/or `codex` CLIs installed if testing live cross-model invocations.

### Running Tests
PeerAgent uses Python's standard `unittest` framework:

```bash
# Run the entire test suite
python3 -m unittest discover -s tests -v

# Run a specific test class or method
python3 -m unittest tests.test_peer.TestPeerCore
```

### Smoke Testing the CLI
Verify that local CLI commands execute cleanly:

```bash
./bin/peer --help
./bin/peer doctor
./bin/peer stats
```

---

## 📝 Code Style & Guidelines

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions for Python code.
- Ensure all subprocess calls properly manage environment isolation (`child_env()`) and avoid shell injection vulnerabilities.
- When adding or modifying slash commands or skills, test both macOS and Linux POSIX environments.
- Keep documentation bilingual when adding major features (update both `README.md` and `README_CN.md`).

---

## 🚀 Pull Request Workflow

1. Fork the repository and create a feature branch (`git checkout -b feature/my-feature`).
2. Implement your changes with clear, focused commits.
3. Add unit tests in `tests/test_peer.py` covering new behavior or fixed bugs.
4. Run the full test suite and verify all tests pass.
5. Open a Pull Request against `main` using the provided PR template.

Thank you for helping build a safer, faster, subscription-native multi-agent mesh!
