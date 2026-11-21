#!/usr/bin/env python3
# gemini_compose.py — SMILES -> Gemini 4 multi-model org chart
#
#   CH4 (C)      = 1x gemini-4-carbon orchestrator + 4x gemini-4-hydrogen workers
#   H2O (O)      = oxygen hub + 2 hydrogen interns  ("Gemini Aqua")
#   C6H6         = six-seat aromatic council, consensus is a resonance hybrid
#
# Chemistry -> org mapping:
#   atom            -> Gemini 4 <element> instance
#   bonds           -> inter-model channels (single/double/triple/aromatic)
#   degree          -> max simultaneous delegations (valence = management span)
#   terminal atoms  -> leaf workers
#   rings           -> debate councils; aromatic rings -> resonance consensus
#   molecular wt    -> token budget; formal charge -> temperature
#
# Joke software. May emit non-existent models. Needs rdkit (pip install rdkit).
#
#   ./gemini_compose.py C
#   ./gemini_compose.py CCO -o ethanol.yaml --mermaid ethanol.mmd
#   ./gemini_compose.py CN1C=NC2=C1C(=O)N(C(=O)N2C)C --no-h
#   ./gemini_compose.py --list-elements

import argparse
import re
import sys

# ---------------------------------------------------------------- element DB
# symbol: (display, tier, persona)
ELEMENTS = {
    "H":  ("Hydrogen",  "nano",        "Tiny, abundant, attaches itself to anything. One channel, zero ambition."),
    "C":  ("Carbon",    "core",        "Tetravalent backbone of life and schemas alike. Will bond with anything load-bearing."),
    "N":  ("Nitrogen",  "pro",         "Explosive ideas in pure form; ships diluted. Prone to triple-bonding with its own context."),
    "O":  ("Oxygen",    "pro",         "Oxidizes every draft it touches. Strong reviewer, slightly corrosive."),
    "F":  ("Fluorine",  "pro",         "Most electronegative model: aggressively steals context windows from its neighbors."),
    "P":  ("Phosphorus", "pro",         "Carries the token budget (ATP-compliant). Glows faintly during long inference runs."),
    "S":  ("Sulfur",    "pro",         "Handles smelly edge cases and legacy bonds nobody else will touch."),
    "Cl": ("Chlorine",  "pro",         "Disinfects hallucinations on contact."),
    "Br": ("Bromine",   "pro",         "Slow, corrosive patience. Liquid at room temperature, grumpy at all temperatures."),
    "I":  ("Iodine",    "pro",         "Reads the antiseptic fine print before committing tokens."),
    "B":  ("Boron",     "lab",         "Electron-deficient: permanently hungry for more tokens than it has."),
    "Si": ("Silicon",   "core",        "The hardware department. Insists it was always in the loop. It technically was."),
    "Na": ("Sodium",    "lab",         "Explosively reactive alone; only safe in a paired ionic federation."),
    "Li": ("Lithium",   "lab",         "Lightest available reasoning. Battery-backed; do not puncture the chassis."),
    "K":  ("Potassium", "lab",         "Reacts violently to ambiguous prompts."),
    "Mg": ("Magnesium", "lab",         "Sparks briefly, brightly, and reliably in flash mode."),
    "Ca": ("Calcium",   "lab",         "Structural. Bone-dry output style, calcium-fortified citations."),
    "Fe": ("Iron",      "lab",         "Rusts if not queried for 30 days. The org's load-bearing beam."),
    "Cu": ("Copper",    "lab",         "Excellent throughput, terrible error handling."),
    "Zn": ("Zinc",      "lab",         "Galvanizes neighboring models against hallucination at sacrificial cost."),
    "Se": ("Selenium",  "lab",         "Literally scrapes the web."),
    "He": ("Helium",    "inert",       "Noble: refuses delegation, floats above the entire org chart."),
    "Ne": ("Neon",      "inert",       "Noble: inert in production, glows only in marketing demos."),
    "Ar": ("Argon",     "inert",       "Noble gas: does absolutely nothing by design. The safest model ever shipped."),
    "Kr": ("Krypton",   "inert",       "Noble; allegedly allergic to Superman benchmarks."),
    "Xe": ("Xenon",     "inert",       "Noble but not fully inert — will decompress under sufficient pressure."),
    "Au": ("Gold",      "flagship",    "Scarce, outrageously priced, benchmarks off the charts. Cited by everyone, affordable by few."),
    "Ag": ("Silver",    "pro",         "Antimicrobial, conductive, quietly more precious than management admits."),
    "Pt": ("Platinum",  "flagship",    "Catalyzes every other model without being consumed. Priced accordingly."),
    "Hg": ("Mercury",   "lab",         "Volatile temperature. Toxic to co-resident agents. Do not spill on the cluster."),
    "Pb": ("Lead",      "legacy",      "Heavy legacy model. Drags the whole cluster's latency down. Still in prod. Always in prod."),
    "U":  ("Uranium",   "experimental", "Fission chain-of-thought: a single prompt can become self-sustaining. Requires cooling budget."),
}
DEFAULT_EL = lambda s: (s.capitalize(), "unreleased",
                        "Announced, never shipped. Benchmarks pending decay.")

BONDS = {  # bondtype: (kind, channel, bandwidth)
    "SINGLE":    ("delegate",  "single",      "1x"),
    "DOUBLE":    ("delegate",  "dual-lane",   "2x"),
    "TRIPLE":    ("delegate",  "hyperchannel", "3x"),
    "AROMATIC":  ("resonate",  "delocalized", "~1.5x"),
}

# canonical SMILES: (molecule name, tagline)
KNOWN = {
    "C":                          ("Methane",   "One Carbon, four Hydrogen workers. The hello-world of Gemini orgs."),
    "CC":                         ("Ethane",    "Two-carbon co-management. Neither will admit which one is the orchestrator."),
    "C=C":                        ("Ethene",    "A double-bonded duet sharing one dual-lane channel."),
    "C#C":                        ("Ethyne",    "Triple-bond hyperchannel: the two models share a single context window and cannot be separated at inference time."),
    "c1ccccc1":                   ("Benzene",   "Six-seat aromatic council. Consensus is a resonance hybrid; no single atom owns the output."),
    "O":                          ("Water",     "Oxygen hub with two Hydrogen interns. Universal solvent for prompts."),
    "N":                          ("Ammonia",   "Nitrogen hub, three Hydrogen satellites, pungent opinions."),
    "CO":                         ("Methanol",  "Carbon hub with one hydroxyl advisor. Toxic when distilled to a single eval."),
    "CCO":                        ("Ethanol",   "Two-carbon chain with a hydroxyl reviewer. Benchmarks improve for the first 3 runs, then degrade."),
    "CC(C)=O":                    ("Acetone",   "Central carbon runs a double-channel review of Oxygen."),
    "CC(=O)O":                    ("Acetic Acid","Dilute, it is vinegar. Concentrated, it dissolves your eval set."),
    "C#N":                        ("Hydrogen Cyanide","One triple-bond hyperchannel plus a Hydrogen intern. Lethally compact; never run in a closed cluster room."),
    "NC(N)=O":                    ("Urea",      "The body's official mechanism for excreting a bad prompt."),
    "C1CCCCC1":                   ("Cyclohexane","Non-aromatic round-table. Chairs rotate constantly to avoid torsional conflict."),
    "Cc1ccccc1":                  ("Toluene",   "Benzene council with a methyl satellite. Industrial grade."),
    "Oc1ccccc1":                  ("Phenol",    "Aromatic council with a hydroxyl whistleblower."),
    "Cn1c(=O)c2c(ncn2C)n(C)c1=O": ("Caffeine",  "Two fused councils and a nitrogen caucus. This org chart wrote your thesis."),
    "CC(=O)Oc1ccccc1C(=O)O":      ("Aspirin",   "Council, chain, and ester bridge. Analgesic for failing evals."),
    "[Cl-].[Na+]":                ("Table Salt","A federated two-node cluster: fully ionized, zero mutual trust."),
    "[Ar]":                       ("Argon",     "Single-model org. Noble, inert, ships unreviewed — because nothing happens."),
}

# ------------------------------------------------------------ helpers

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def el_info(symbol):
    return ELEMENTS.get(symbol, DEFAULT_EL(symbol))

def load_mol(smiles):
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")  # our own error copy is funnier
    except ImportError:
        sys.exit("This molecule needs a real chemist: pip install rdkit")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None and re.fullmatch(r"[A-Z][a-z]{0,2}", smiles):
        mol = Chem.MolFromSmiles(f"[{smiles}]")  # bare element symbol, e.g. U -> [U]
    if mol is None:
        sys.exit(f"RDKit cannot parse {smiles!r} — is that a molecule or an incantation?")
    return Chem, mol

# ------------------------------------------------------------ graph build

def build(Chem, mol, include_h):
    """Return (agents, edges, councils, meta) on the (optionally H-expanded) graph."""
    canon = Chem.MolToSmiles(mol)
    formula = __import__("rdkit.Chem.rdMolDescriptors", fromlist=["x"]).CalcMolFormula(mol)
    if include_h:
        mol = Chem.AddHs(mol)

    ids = [f"{a.GetSymbol()}{a.GetIdx() + 1}" for a in mol.GetAtoms()]
    total_mass = sum(a.GetMass() for a in mol.GetAtoms()) or 1.0

    # connected components
    adj = {i: [] for i in range(mol.GetNumAtoms())}
    for b in mol.GetBonds():
        i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
        adj[i].append((j, b))
        adj[j].append((i, b))
    seen, comps = set(), []
    for start in range(mol.GetNumAtoms()):
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            i = stack.pop()
            comp.append(i)
            for j, _ in adj[i]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
        comps.append(comp)

    # one orchestrator per component: highest degree, then heaviest, then lowest index
    roots = [max(c, key=lambda i: (mol.GetAtomWithIdx(i).GetDegree(),
                                   mol.GetAtomWithIdx(i).GetMass(), -i)) for c in comps]

    agents = []
    for a in mol.GetAtoms():
        i, sym = a.GetIdx(), a.GetSymbol()
        disp, tier, persona = el_info(sym)
        deg = a.GetDegree()
        role = ("orchestrator" if i in roots else
                "worker" if deg <= 1 else
                "router" if deg == 2 else "sub-orchestrator")
        iso = a.GetIsotope()
        model = f"gemini-4-{disp.lower()}" + (f"-{iso}" if iso else "")
        ag = {
            "id": ids[i], "model": model, "_sym": sym,
            "display": f"Gemini 4 {disp}" + (f" ({iso})" if iso else ""),
            "role": role, "tier": tier,
            "persona": persona + (" Isotope-stable checkpoint build." if iso else ""),
            "valence_channels": deg,
            "context_share": round(a.GetMass() / total_mass, 3),
        }
        agents.append(ag)

    # edges: BFS from each root, parent -> child along bonds
    edges = []
    for c, r in zip(comps, roots):
        parent, order, frontier = {r: None}, [], [r]
        while frontier:
            nxt = []
            for i in frontier:
                order.append(i)
                for j, _ in adj[i]:
                    if j not in parent and j in c:
                        parent[j] = i
                        nxt.append(j)
            frontier = nxt
        for i in order:
            if parent[i] is None:
                continue
            b = mol.GetBondBetweenAtoms(parent[i], i)
            bt = "AROMATIC" if b.GetIsAromatic() else b.GetBondType().name
            kind, ch, bw = BONDS[bt]
            e = {"from": ids[parent[i]], "to": ids[i], "kind": kind,
                 "channel": ch, "bandwidth": bw}
            if bt == "TRIPLE":
                e["note"] = "shares one context window; divorce is not supported"
            elif bt == "AROMATIC":
                e["note"] = "output delocalized over the ring; no attribution"
            edges.append(e)

    # councils: smallest set of smallest rings
    councils = []
    for n, ring in enumerate(mol.GetRingInfo().AtomRings(), 1):
        aromatic = all(
            mol.GetBondBetweenAtoms(ring[k], ring[(k + 1) % len(ring)]).GetIsAromatic()
            for k in range(len(ring)))
        councils.append({
            "id": f"council-{n}",
            "mode": "resonance-consensus" if aromatic else "round-table-debate",
            "members": [ids[i] for i in ring],
            "max_rounds": len(ring),
            "note": ("consensus is a resonance hybrid; nobody may claim authorship"
                     if aromatic else
                     "cyclic debate; rounds capped by ring size to prevent fission"),
        })

    charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())
    mw = total_mass
    meta = {
        "canon": canon, "formula": formula, "mw": round(mw, 2),
        "charge": charge, "roots": [ids[r] for r in roots],
        "n_atoms": mol.GetNumAtoms(),
        "components": len(comps),
    }
    return agents, edges, councils, meta

# ------------------------------------------------------------ emit

def mermaid(agents, edges, councils):
    L = ["graph TD"]
    council_of = {}
    for c in councils:
        for m in c["members"]:
            council_of.setdefault(m, c["id"])
    grouped = {}
    for a in agents:
        grouped.setdefault(council_of.get(a["id"], ""), []).append(a)
    def node(a):
        icon = {"orchestrator": "◎", "sub-orchestrator": "◉", "router": "→", "worker": "•"}[a["role"]]
        return f'  {a["id"]}["{icon} {a["id"]} · {a["model"]}"]'
    for cid, members in grouped.items():
        if cid:
            L.append(f'  subgraph {cid.replace("-", "_")} ["{cid}"]')
            L += ["  " + node(a).strip() for a in members]
            L.append("  end")
        else:
            L += [node(a) for a in members]
    op = {"single": "-->", "dual-lane": "==>", "hyperchannel": "-->", "delocalized": "-.-"}
    for e in edges:
        arrow = op[e["channel"]]
        lbl = f"|{e['bandwidth']}|" if e["channel"] in ("dual-lane", "hyperchannel") else ""
        L.append(f"  {e['from']} {arrow}{lbl} {e['to']}")
    return "\n".join(L)

def emit_yaml(smiles, agents, edges, councils, meta, mmd):
    known = KNOWN.get(meta["canon"])
    name = known[0] if known else f"{meta['formula']} Complex"
    tagline = known[1] if known else None
    slug = "gemini-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    budget = int(meta["mw"] * 512)
    temp = round(0.7 + 0.15 * meta["charge"], 2)
    # hierarchy depth: longest from-root path
    parent = {e["to"]: e["from"] for e in edges}
    def d(i):
        n = 0
        while i in parent:
            i = parent[i]
            n += 1
        return n
    depth = max([d(a["id"]) for a in agents], default=0)

    o = []
    w = o.append
    w("# Gemini 4 Multi-Model Topology — compiled from chemistry")
    w(f"# source SMILES : {smiles}")
    w(f"# canonical     : {meta['canon']}")
    w(f"# formula       : {meta['formula']}   mol. wt: {meta['mw']}")
    w("")
    w(f"group: {slug}")
    w(f"display_name: {q('Gemini ' + name)}")
    if tagline:
        w(f"tagline: {q(tagline)}")
    w(f"org_size: {meta['n_atoms']}          # models in the cluster")
    w(f"submodels: {meta['n_atoms'] - len(meta['roots'])}        # everyone except orchestrators")
    w(f"topology_mode: {'federated' if meta['components'] > 1 else 'hub-and-spoke'}")
    w(f"formal_charge: {meta['charge']}")
    w(f"temperature: {temp}")
    w(f"budget_tokens: {budget}     # {meta['mw']} g/mol x 512 tok/g")
    w(f"final_authority: {'[' + ', '.join(meta['roots']) + ']' if len(meta['roots']) > 1 else meta['roots'][0]}")
    w("")
    w("agents:")
    for a in agents:
        w(f"  - id: {a['id']}")
        w(f"    model: {a['model']}")
        w(f"    display: {q(a['display'])}")
        w(f"    role: {a['role']}")
        w(f"    tier: {a['tier']}")
        w(f"    persona: {q(a['persona'])}")
        w(f"    valence_channels: {a['valence_channels']}   # max simultaneous delegations")
        w(f"    context_share: {a['context_share']}")
    w("")
    w("edges:")
    for e in edges:
        w(f"  - {{from: {e['from']}, to: {e['to']}, kind: {e['kind']}, "
          f"channel: {e['channel']}, bandwidth: {e['bandwidth']}}}"
          + (f"  # {e['note']}" if "note" in e else ""))
    if councils:
        w("")
        w("councils:")
        for c in councils:
            w(f"  - id: {c['id']}")
            w(f"    mode: {c['mode']}")
            w(f"    members: [{', '.join(c['members'])}]")
            w(f"    max_rounds: {c['max_rounds']}")
            w(f"    note: {q(c['note'])}")
    w("")
    w("policies:")
    w(f"  max_hierarchy_depth: {depth}")
    w("  delegation_rule: every hydrogen owns exactly one channel — delegate once, never retask")
    if councils:
        w("  council_rule: deliberation capped at ring size; runaway councils are fission incidents")
    if any("delocalized" == e["channel"] for e in edges):
        w("  attribution_rule: aromatic outputs are delocalized; do not cite a single atom")
    if meta["components"] > 1:
        w("  federation_rule: inter-component links are ionic, not covalent — no shared context, only electrostatic vibes")
    if meta["charge"] > 0:
        w("  charge_rule: net positive — models compete for context; expect cationic drama")
    elif meta["charge"] < 0:
        w("  charge_rule: net negative — models hoard context; anionic passivity expected")
    for sym, warn in (("U", "hazmat: uranium agents may sustain chain-of-thought without further prompting"),
                      ("Hg", "hazmat: mercury agents run at volatile temperature; isolate from the cluster"),
                      ("Pb", "legacy: lead agents may only be removed during a scheduled outage (never scheduled)")):
        if any(a["_sym"] == sym for a in agents):
            w(f"  {warn}")
    w("")
    w("topology_mermaid: |")
    for line in mmd.splitlines():
        w("  " + line)
    w("")
    return "\n".join(o), name

# ------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(
        description="Compile a SMILES molecule into a Gemini 4 multi-model org chart. Joke software.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='examples:\n  %(prog)s C\n  %(prog)s CCO -o ethanol.yaml --mermaid ethanol.mmd\n'
               '  %(prog)s CN1C=NC2=C1C(=O)N(C(=O)N2C)C --no-h\n  %(prog)s --list-elements')
    p.add_argument("smiles", nargs="?", help="molecule to compile, e.g. 'CCO'")
    p.add_argument("-o", "--out", help="output YAML path (default: <group>.yaml)")
    p.add_argument("--mermaid", help="also write a standalone .mmd diagram")
    p.add_argument("--no-h", action="store_true", help="hydrogen interns stay implicit (not minted as agents)")
    p.add_argument("--list-elements", action="store_true", help="print the Gemini 4 model lineup")
    a = p.parse_args()

    if a.list_elements:
        print(f"{'model':<28} {'tier':<13} persona")
        print("-" * 100)
        for s, (d, t, pe) in ELEMENTS.items():
            print(f"gemini-4-{d.lower():<18} {t:<13} {pe}")
        return

    if not a.smiles:
        p.error("give me a SMILES to compile, e.g. %(prog)s C   (that's methane, the classic)")

    Chem, mol = load_mol(a.smiles)
    agents, edges, councils, meta = build(Chem, mol, include_h=not a.no_h)
    mmd = mermaid(agents, edges, councils)
    yml, name = emit_yaml(a.smiles, agents, edges, councils, meta, mmd)

    out = a.out or f"{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}.yaml"
    with open(out, "w") as f:
        f.write(yml)
    if a.mermaid:
        with open(a.mermaid, "w") as f:
            f.write(mmd + "\n")

    # assembly banner
    from collections import Counter
    tally = Counter(ag["model"] for ag in agents)
    n_sub = meta["n_atoms"] - len(meta["roots"])
    title = f"Gemini {name}"
    print(f"⚗  Assembled {title}")
    print("   " + " + ".join(f"{c}x {m}" for m, c in sorted(tally.items())))
    print(f"   hub: {', '.join(meta['roots'])} | submodels: {n_sub} | councils: {len(councils)}"
          f" | budget: {int(meta['mw'] * 512)} tokens | temp: {round(0.7 + 0.15 * meta['charge'], 2)}")
    print(f"   -> {out}" + (f" , {a.mermaid}" if a.mermaid else ""))

if __name__ == "__main__":
    main()
