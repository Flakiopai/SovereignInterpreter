# Chapter 14 — Roadmap

> Non-binding documentation. This chapter does **not** schedule releases or invent runtime behavior.

## Senior engineer

Suggested evolution **themes** that preserve doctrine (ideas only):

1. **Operator observability** — richer structured logs of envelope categories without leaking secrets  
2. **Harder isolation** — optional OS-level containment around runners (still local-first)  
3. **Memory pack UX** — clearer export/import workflows for air-gapped recall  
4. **Playbooks** — incident runbooks for kill-switch, sandbox demotion, model downgrade  
5. **Docs expansion** — handbook deep-dives per module as surfaces stabilize  

Themes that would **violate** doctrine if introduced casually as defaults:

- Cloud-default inference  
- Silent auto-execution of model fences  
- Expanding delete defaults without explicit operator action  

Any future work belongs in the main repo’s code + changelog — not as silent “already shipped” claims in this handbook.

## Beginner

Future improvements should keep the same promises: local by default, ask before running, stay in the sandbox. Treat this chapter as a wish list, not a calendar.

## Explain like I’m 12

```text
  Now (0.3.0)
    sandbox + envelopes + labels + intent gates

  Later (maybe)
    clearer logs / harder walls / nicer memory packs / better manuals

  Not okay as a surprise default
    secret cloud calls / surprise code runs / easy deletes
```

Later we might add better tools. The house rules stay: privacy, ask first, stay in the toy box.

## Repo examples (main SovereignInterpreter)

- Version history: `CHANGELOG.md`  
- Security contact surface: `SECURITY.md`  
- Doctrine demos: `examples/sovereign/`

## Key takeaway

Roadmap ideas must pass the sovereignty test **before** they become code — and this handbook only documents what already shipped elsewhere.

---

← [Tests](13-tests.md) · [Next: Sovereign doctrine →](15-sovereign-doctrine.md)
