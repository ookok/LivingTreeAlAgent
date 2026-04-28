from core.model_election import get_elected_models, print_election_report, detect_hardware

print("检测硬件配置...")
hw = detect_hardware()
vram_gb = hw.gpu_vram_gb if hasattr(hw, "gpu_vram_gb") else 0
has_gpu = hw.has_gpu if hasattr(hw, "has_gpu") else False
print(f"  GPU: {has_gpu}, VRAM: {vram_gb}GB")
ram = getattr(hw, "ram_total_gb", 0)
cores = getattr(hw, "cpu_cores", 0)
print(f"  RAM: {ram:.1f}GB")
print(f"  CPU核心: {cores}")

result = get_elected_models(force_refresh=True)
print_election_report(result)
