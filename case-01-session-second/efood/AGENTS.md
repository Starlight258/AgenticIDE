# efood Guardrail Rules

- R1 WARN: relative import (`from .`)
- R2 BLOCK: shell execution through `os.system` or `subprocess`
- R3 WARN: public function without a docstring
- R4 BLOCK: `print()`
- R5 BLOCK: outbound HTTP through `requests.get/post/put/patch/delete/head/options`
