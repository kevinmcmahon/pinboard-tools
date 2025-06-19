# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# LLM-friendly formats
text: ## Build plain text documentation for LLM consumption
	@uv run --with sphinx sphinx-build -b text "$(SOURCEDIR)" "$(BUILDDIR)/text" $(SPHINXOPTS) $(O)
	@echo "Build finished. The text files are in $(BUILDDIR)/text."

singlehtml: ## Build single HTML file with all documentation
	@uv run --with sphinx sphinx-build -b singlehtml "$(SOURCEDIR)" "$(BUILDDIR)/singlehtml" $(SPHINXOPTS) $(O)
	@echo "Build finished. The single HTML file is in $(BUILDDIR)/singlehtml."

singletext: text ## Build single consolidated text file for LLM consumption
	@echo "Consolidating all text files into single document..."
	@mkdir -p $(BUILDDIR)/singletext
	@find $(BUILDDIR)/text -name "*.txt" -exec cat {} \; > $(BUILDDIR)/singletext/consolidated.txt
	@echo "Consolidated documentation created at $(BUILDDIR)/singletext/consolidated.txt"

llm: singlehtml singletext ## Build LLM-friendly formats
	@echo "LLM-friendly formats built in $(BUILDDIR)/singlehtml and $(BUILDDIR)/singletext/consolidated.txt"

.PHONY: help text singlehtml singletext llm Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
