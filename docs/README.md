# Documentation

This directory contains the source files for the `pynintendoparental` documentation site, which is built using [MkDocs](https://www.mkdocs.org/) with the [Material theme](https://squidfunk.github.io/mkdocs-material/).

## Building the Documentation

### Prerequisites

Install the documentation dependencies:

```bash
pip install -r requirements.docs.txt
```

### Build Commands

**Build the documentation:**
```bash
mkdocs build
```

**Serve the documentation locally:**
```bash
mkdocs serve
```

Then open http://127.0.0.1:8000/pynintendoparental/ in your browser.

**Using justfile (if available):**
```bash
just docs-build  # Build documentation
just docs-serve  # Serve documentation locally
```

## Documentation Structure

```
docs/
├── index.md                    # Home page
├── guide/                      # User guides
│   ├── getting-started.md     # Installation and setup
│   ├── authentication.md      # Authentication guide
│   └── examples.md            # Usage examples
├── api/                       # API reference
│   ├── nintendoparental.md   # Main API class
│   ├── device.md             # Device class
│   ├── player.md             # Player class
│   ├── application.md        # Application class
│   ├── authenticator.md      # Authenticator class
│   ├── enums.md              # Enumerations
│   └── exceptions.md         # Exception classes
├── assets/                    # Static assets
│   └── images/               # Images for documentation
└── stylesheets/              # Custom CSS
    └── extra.css             # Custom styles
```

## Deployment

The documentation is automatically deployed to GitHub Pages when changes are pushed to the `main` branch. The deployment is handled by the `.github/workflows/documentation.yml` workflow.

### Manual Deployment

To manually deploy the documentation to GitHub Pages:

```bash
mkdocs gh-deploy
```

This command will:
1. Build the documentation
2. Push the built site to the `gh-pages` branch
3. GitHub Pages will serve the content from that branch

## Writing Documentation

### Adding New Pages

1. Create a new Markdown file in the appropriate directory
2. Add the page to the `nav` section in `mkdocs.yml`

Example:
```yaml
nav:
  - Home: index.md
  - Your New Page: path/to/new-page.md
```

### Code Examples

Use fenced code blocks with language specification:

````markdown
```python
import asyncio
from pynintendoparental import NintendoParental

async def main():
    # Your code here
    pass
```
````

### API Documentation

API reference pages use mkdocstrings to automatically generate documentation from docstrings:

```markdown
::: pynintendoparental.ClassName
    options:
      show_root_heading: true
      show_source: true
      heading_level: 2
```

### Admonitions

You can use admonitions to highlight important information:

```markdown
!!! note
    This is a note.

!!! warning
    This is a warning.

!!! tip
    This is a tip.
```

## Theme Configuration

The documentation uses the Material for MkDocs theme with the following features:

- **Navigation**: Instant loading, tracking, tabs, sections, and expansion
- **Search**: Suggestions and highlighting
- **Code**: Copy button for code blocks
- **Dark Mode**: Toggle between light and dark themes
- **Colors**: Blue primary with light blue accent

For more configuration options, see the [Material for MkDocs documentation](https://squidfunk.github.io/mkdocs-material/).

## Custom Styling

Custom CSS is located in `docs/stylesheets/extra.css`. This file includes styles to:
- Preserve newlines in content areas
- Handle word breaking for better readability

## Assets

### Logo and Favicon

To add a custom logo and favicon:

1. Add your logo to `docs/assets/images/logo.png`
2. Add your favicon to `docs/assets/images/favicon.png`
3. Uncomment the following lines in `mkdocs.yml`:
   ```yaml
   logo: assets/images/logo.png
   favicon: assets/images/favicon.png
   ```

## Troubleshooting

### Build Errors

If you encounter build errors:

1. Ensure all dependencies are installed: `pip install -r requirements.docs.txt`
2. Check that all internal links in Markdown files are valid
3. Run `mkdocs build --strict` to see detailed error messages

### Broken Links

MkDocs will warn about broken links when using `--strict` mode. Check the build output for details.

## Contributing

When contributing to the documentation:

1. Ensure your changes build without errors
2. Follow the existing documentation structure and style
3. Update the navigation in `mkdocs.yml` if adding new pages
4. Test your changes locally before submitting a PR

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [Markdown Guide](https://www.markdownguide.org/)
- [Python Docstring Conventions](https://peps.python.org/pep-0257/)
