# Contributing to A.R.I.A.

First off, thanks for taking the time to contribute! A.R.I.A. is designed to be an extensible, open-source AI assistant, and your help makes it better.

## How to Contribute

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally: `git clone https://github.com/your-username/aria.git`
3. **Create a new branch** for your feature or bug fix: `git checkout -b feature/my-awesome-feature`
4. **Make your changes** and commit them with clear, descriptive messages.
5. **Push your branch** to your fork: `git push origin feature/my-awesome-feature`
6. **Open a Pull Request** against the `main` branch of this repository.

## Development Guidelines

- **Code Style:** We follow standard PEP 8 for Python and standard Prettier formatting for TypeScript.
- **Testing:** Please test your tools or modules locally before submitting. 
- **Tool Creation:** If you are adding a new tool, make sure to use the `@aria_tool` decorator in `core/tool_registry.py` and document its parameters fully, as this dictates how the LLM interacts with it.
- **Agentic Loop:** Be mindful of the self-reflection loop. Tools should return clear, textual feedback (success or failure) so the planner can reflect and recover if needed.

## Reporting Bugs

If you find a bug, please open an issue with:
- A clear title and description.
- Steps to reproduce.
- Your OS, Python version, and any relevant logs.

Happy building!
