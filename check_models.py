from mlops.registry import registry
models = registry.list_models(status='candidate')
print(f'Models ready: {len(models)}')
for m in models:
    print(f'  {m.get("symbol","?")} | {m.get("version","?")}')
