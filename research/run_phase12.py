import os
from research.adversarial_emulator import AdversarialEmulator
from research.queue_physics import QueuePhysics
from research.toxicity_classifier import ToxicityClassifier
from research.adversarial_ev import AdversarialEV

def run_phase12():
    print("=========================================")
    print(" PHASE 12: Adversarial Execution Model   ")
    print("=========================================")
    
    # Instantiate modules
    emulator = AdversarialEmulator(my_latency_rank=2) # We are Tier-2
    queue = QueuePhysics()
    toxicity = ToxicityClassifier()
    ev_calc = AdversarialEV()
    
    report = ["# Phase 12: Adversarial Execution Alpha Report", ""]
    report.append("This report documents the Adversarial Execution Alpha Layer. We simulated competition for liquidity, queue probability, and flow toxicity to determine if our Phase 11 Liquidity Intelligence yields a truly executable edge.")
    
    # We bring in the "Liquidity Vacuum" signal from Phase 11
    # Tick 3: OBI = 0.92, CVD = 70, expected raw move = 50 bps.
    signal_expected_move = 0.0050 # 50 bps
    impact_cost = 0.000758        # ~7.5 bps
    latency_cost = 0.0002         # 2 bps
    
    print("\n1. Flow Toxicity Classification")
    # Simulate LPR (Liquidity Persistence Ratio)
    # The liquidity vanished almost instantly when price didn't move -> LPR = 0.1
    lpr = 0.1
    flow_class = toxicity.classify_flow(obi=0.92, lpr=lpr, price_follow_through=False)
    print(f"LPR: {lpr} | Classification: {flow_class}")
    
    report.append("\n## 1. Toxicity Classification")
    report.append(f"- **Liquidity Persistence Ratio (LPR)**: `{lpr}`")
    report.append(f"- **Flow Classification**: `{flow_class}`")
    
    if flow_class == 'TOXIC_SPOOF':
        print("\n [!] SIGNAL REJECTED: Flow is toxic/spoofed. Expected move will likely fail.")
        report.append("\n> [!WARNING]")
        report.append("> The perceived Liquidity Vacuum was classified as **TOXIC SPOOFING**. Liquidity vanished without price movement. Signal rejected to avoid adverse selection.")
    
    print("\n2. Adversarial Preemption")
    # What if it was informed flow? Let's simulate the latency race.
    p_preempt = emulator.calculate_preemption_prob(signal_visibility=0.9, volatility=0.2)
    print(f"Probability of being preempted by Tier-1 HFT: {p_preempt*100:.2f}%")
    
    report.append("\n## 2. Adversarial Preemption")
    report.append("- We operate at **Latency Rank 2** (Standard Colocation).")
    report.append(f"- **Probability of Preemption by Tier-1**: `{p_preempt*100:.2f}%`")
    
    print("\n3. Queue Position & Fill Probability")
    # Assume we queue up 10 lots deep, incoming flow is 5 lots
    p_fill = queue.estimate_fill_probability(queue_depth=10.0, incoming_aggressive_flow=5.0, liquidity_decay_factor=0.8)
    print(f"Probability of Fill: {p_fill*100:.2f}%")
    
    report.append("\n## 3. Queue Physics & Fill Probability")
    report.append(f"- **Estimated Fill Probability**: `{p_fill*100:.2f}%` (Queue Depth: 10, Incoming Flow: 5)")
    
    print("\n4. Adversarial EV Calculation")
    net_ev = ev_calc.calculate_net_ev(p_fill, p_preempt, signal_expected_move, impact_cost, latency_cost)
    print(f"Net Adversarial EV: {net_ev*10000:.2f} bps")
    
    report.append("\n## 4. Net Adversarial Expected Value (EV)")
    report.append(f"Net EV calculation adjusts the raw expected move by the probability of winning the latency race, getting filled in the queue, and subtracts impact and latency costs.")
    report.append(f"- **Raw Expected Move**: `50.00 bps`")
    report.append(f"- **Impact + Latency Cost**: `9.58 bps`")
    report.append(f"- **Net Adversarial EV**: `{net_ev*10000:.2f} bps`")
    
    print("\n=========================================")
    if net_ev > 0 and flow_class != 'TOXIC_SPOOF':
        print("VERDICT: TRUE HFT ALPHA (DEPLOY)")
        report.append("\n> [!SUCCESS]")
        report.append("> **VERDICT: TRUE HFT ALPHA (DEPLOY)**. The signal survives adversarial preemption, queue physics, toxicity checks, and execution costs.")
    else:
        print("VERDICT: ADVERSE SELECTION (REJECT)")
        report.append("\n> [!CAUTION]")
        report.append("> **VERDICT: ADVERSE SELECTION (REJECT)**. The signal fails to produce positive expectancy under competitive adversarial conditions.")

    with open("docs/adversarial_alpha_report.md", "w", encoding='utf-8') as f:
        f.write("\n".join(report))
        
    print("\nPhase 12 Complete. Report saved to docs/adversarial_alpha_report.md")

if __name__ == "__main__":
    os.environ['PYTHONPATH'] = "."
    run_phase12()
