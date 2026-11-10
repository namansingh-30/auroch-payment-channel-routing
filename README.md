# Auroch: Auction-Based Multipath Routing for Payment Channel Networks

## Project overview

This project implements the core Auroch routing workflow for
Lightning-style Payment Channel Networks (PCNs), using Python and
NetworkX. The reference paper is **"Auroch: Auction-Based Multipath
Routing for Payment Channel Networks" (ASIA CCS 2024)**.

This README documents the work completed so far, current assumptions,
remaining work, and GitHub handover instructions.

## 1. Dataset and graph construction

-   Snapshot: November 27, 2021.
-   Local dataset used: `Auroch/data/lngraph_2021_11_27__00_00.json.zst`
    (a parsed JSON version was also used during development).
-   Paper-reported snapshot: 18,331 nodes and 80,918 channels.
-   Current parsed dataset: 18,310 nodes and 80,743 channels.
-   The count difference should be investigated/documented if exact
    reproduction is required.

### Graph representation

A NetworkX `MultiGraph` is used to preserve parallel physical channels.
Channel attributes include:

-   `channel_id`
-   `node1_pub`, `node2_pub`
-   `capacity`
-   `node1_policy`, `node2_policy`

`node1_policy` applies to `node1_pub -> node2_pub`; `node2_policy`
applies in the reverse direction. Missing policies are treated as
unknown/unavailable, and disabled directions are not used for
forwarding.

### Liquidity assumption --- important

The public topology snapshot provides channel capacities and policies,
but not current local directional balances after transactions. The paper
notes that local balances change due to transactions and are not
publicly available.

The current simulation initializes liquidity 50:50:

``` python
liquidity_1_to_2 = capacity // 2
liquidity_2_to_1 = capacity - liquidity_1_to_2
```

**This is a simulation assumption, not a confirmed initialization rule
specified by the paper.** The next contributor must investigate whether
channel-opening balance data is available. If it is not, retain a
clearly documented and defensible simulation assumption; do not claim
that 50:50 is the paper's exact method.

## 2. Implementation completed

  -----------------------------------------------------------------------
  Component                           Current implementation
  ----------------------------------- -----------------------------------
  Network graph                       Parsed snapshot into NetworkX
                                      `MultiGraph`

  Parallel channels                   Preserved with `MultiGraph`

  Directional policies                Uses node1/node2 directional
                                      policies

  Liquidity simulation                50:50 initialization assumption;
                                      balances update after payments

  RREQ                                BFS-based path discovery and
                                      predecessor tracking

  RREP                                Reverse-path generation,
                                      propagation, route extension,
                                      completed-route detection

  AUC                                 Auction messages with path
                                      information, `WinPrice`, `tau_fee`,
                                      `ResPrice`

  Bidding                             Rule 1 and Rule 2 calculations from
                                      the paper

  Equation 6                          Auction allocation solved using
                                      SciPy `linprog`

  Auction validation                  Capacity/bid-capacity constraints
                                      and optimality cross-check

  Equation 7                          Payment allocation across completed
                                      routes using linear programming

  Shared-channel constraints          Prevents routes sharing a directed
                                      physical channel from collectively
                                      exceeding its liquidity

  Payment execution                   Exact channel-ID lookup,
                                      direction/policy/liquidity checks,
                                      directional balance update

  Transaction safety                  Executes on a temporary graph and
                                      commits only if the full payment
                                      succeeds

  Final audit                         Checks capacity preservation,
                                      non-negative balances, and expected
                                      directional changes
  -----------------------------------------------------------------------

### Implementation details

-   **RREQ:** BFS discovers shortest paths and stores predecessor
    information. Graph adjacency is used for discovery; policy and
    liquidity checks occur in later stages.
-   **RREP:** Route information propagates backward from destination
    toward source. The source detects completed routes when RREPs reach
    it.
-   **AUC:** Carries transaction/auction identifiers, path information,
    capacity, `WinPrice`, `tau_fee`, and `ResPrice`. The current
    relationship is `ResPrice = WinPrice + tau_fee`.
-   **Bidding:** Rule 1 and Rule 2 equations discussed from the paper
    are implemented.
-   **Equation 6:** Solved using SciPy linear programming. Exact
    physical channel identifiers are retained for subsequent stages.
-   **Equation 7:** Allocates payment across routes using route cost and
    capacity. Additional shared directed-channel constraints handle
    routes that share a physical channel.
-   **Payment:** Uses exact channel IDs; checks direction, policy,
    disabled status, positive amount, and sufficient directional
    liquidity. Liquidity is moved to the reverse direction and channel
    capacity is preserved.

## 3. Latest successful end-to-end test

The latest recorded run completed the simulated routing and payment
workflow:

  Test item                                       Result
  --------------------------------------- --------------
  Routing rounds                                       2
  AUC messages                                         6
  BID messages                                         6
  Auction allocation records                           6
  Completed routes                                     3
  Requested payment                         100,000 sats
  Route 1 allocation                         50,000 sats
  Route 2 allocation                         50,000 sats
  Route 3 allocation                              0 sats
  Auction LP checks                           6/6 passed
  Channels checked in global validation           80,743
  Invalid channels in global validation                0
  Final used-channel liquidity audit              Passed

The payment was executed over Route 1 and Route 2. Route 3 received zero
allocation. The audit reported that checked channels preserved capacity,
had non-negative balances, and matched expected directional changes.

**This is a successful single-payment simulation, not a reproduction of
the paper's full experimental evaluation.**

## 4. Current limitations / incomplete work

1.  **Liquidity initialization:** 50:50 is an assumption. Investigate
    channel-opening balance data and document the chosen method.
2.  **Full experimental evaluation:** The current test is one
    100,000-satoshi payment. The paper's multi-transaction experiments
    are not yet reproduced.
3.  **ECDSA:** The paper uses ECDSA for signature creation and
    verification. The current code still has placeholder/incomplete
    cryptographic signing and verification.
4.  **Dynamic `tau_fee`:** Intentionally deferred until after baseline
    paper experiments. The current code uses a random value from 1--10;
    verify the exact baseline fee configuration and units against the
    paper.
5.  **Fee-aware Lightning semantics:** The current simulator transfers
    the same allocated amount at every hop. Real Lightning forwarding
    requires fee-aware amount propagation.
6.  **Comparison protocols:** The paper compares Auroch with other
    routing schemes; those baselines have not yet been fully reproduced.
7.  **Reproducibility:** Add fixed/random seeds, experiment
    configuration, raw-result storage, and consistent logging.
8.  **Paper comparison:** Generate metrics/graphs and document
    differences caused by dataset counts, liquidity assumptions, or
    unavailable data.

## 5. Work plan for the next contributor

Follow this order. **Do not implement dynamic `tau_fee` until the
baseline experiments and graphs are complete.**

### Phase A --- Verify liquidity initialization

1.  Read the paper's dataset and experiment setup carefully.
2.  Check whether the snapshot or referenced sources provide
    channel-opening balances.
3.  Do not describe 50:50 as the paper's method unless the paper
    explicitly specifies it.
4.  If actual balances are unavailable, select a documented simulation
    assumption and explain its limitations.
5.  Ensure every run starts from a clean, reproducible graph state.

### Phase B --- Reproduce the paper's baseline experiments

The paper's experiment setup describes:

-   Lightning Network snapshot dated November 27, 2021.
-   Transaction counts: **5,000, 7,000, and 9,000**.
-   Randomly selected source and destination nodes.
-   Transaction amounts sampled randomly from a Bitcoin
    transaction-volume trace.
-   Base fee: **1 satoshi** along each path.
-   Rate fee: randomly sampled in **\[0, 10\]** (verify units and exact
    interpretation against the paper).
-   Channel capacities scaled by **30×, 50×, and 70×**.
-   Results averaged over **20 runs**.

The paper explains that the Lightning snapshot does not include
transaction counts and amounts. It uses Ripple PCN transaction counts
for scalability experiments and Bitcoin transaction-volume trace data
for payment amounts.

### Phase C --- Implement metrics and plots

Implement the metrics using the paper's exact definitions:

**Success ratio**

``` text
successfully routed payments / total attempted payments
```

**Success volume**

``` text
amount of successful payments / amount of all attempted payments
```

**Routing cost**

``` text
total routing cost of successful transactions / total successfully routed payment volume
```

Verify exact definitions and units from the paper before finalizing.

Generate plots across transaction counts and channel-capacity settings.
Average each metric over 20 runs. Save raw per-run results and averaged
results (for example, CSV files).

### Phase D --- Compare with paper

1.  Recreate relevant paper figures as closely as available data allows.
2.  Compare trends and numerical results.
3.  Document differences due to unavailable balance data, dataset count
    differences, and implementation assumptions.
4.  Preserve baseline results before changing the algorithm.

### Phase E --- Dynamic `tau_fee` extension (only after baseline)

1.  Define a mathematical function for dynamic `tau_fee` based on the
    agreed liquidity/capacity condition.
2.  Specify boundary conditions and expected behavior.
3.  Implement it in the auction stage.
4.  Rerun the same experiment configuration.
5.  Compare baseline and dynamic-fee results using the same
    configurations/seeds.
6.  Plot changes in success ratio, success volume, and routing cost.

### Phase F --- Other remaining protocol work

-   Implement and test ECDSA signing and verification.
-   Verify protocol messages and equations line-by-line against the
    paper.
-   Review fee-aware amount propagation at every payment hop.
-   Implement comparison protocols if required by the research
    objective.

## 6. Suggested project structure

The actual local filenames may differ. Keep current working filenames
until imports and paths are checked.

``` text
Auroch/
├── data/
│   └── lngraph_2021_11_27__00_00.json.zst
├── rreq.py
├── rrep.py
├── auction.py
├── bidding.py
├── auction_result.py
├── route_allocation.py
├── payment.py
├── liquidity(5).py       # or the latest working main simulation file
├── README.md
├── requirements.txt
├── results/
│   ├── raw/
│   └── plots/
└── .gitignore
```

Do not rename or move files until imports and dataset paths have been
checked.

## 7. Running the current implementation

1.  Open the project folder in VS Code or a terminal.
2.  Activate the Python environment used for development.
3.  Install dependencies listed in `requirements.txt` (create/update
    this file based on actual imports).
4.  Confirm the dataset path in the main script.
5.  Run the latest working main simulation script. For example:

``` bash
python "liquidity(5).py"
```

The main filename may differ. Use the latest version that produced the
successful end-to-end test.

Likely dependencies include `networkx`, `numpy`, `scipy`, `matplotlib`,
and `zstandard`. Confirm exact packages and versions from the actual
source files before writing `requirements.txt`.

## 8. Uploading the project to GitHub

### Before uploading

1.  Put source files in one project folder.
2.  Save this file as `README.md` in the repository root.
3.  Add a `requirements.txt` with actual dependencies.
4.  Add a `.gitignore`.
5.  Do not upload virtual environments, caches, temporary outputs,
    private keys, API tokens, or credentials.
6.  Check the dataset's source and redistribution/license terms. If
    redistribution is not allowed or the file is too large, do not
    commit the dataset. Instead, document its download source and
    expected location under `data/`.

Suggested `.gitignore`:

``` gitignore
__pycache__/
*.py[cod]
.venv/
venv/
env/
.ipynb_checkpoints/
.vscode/
.DS_Store
Thumbs.db
.env
*.pem
*.key
```

### Option A --- GitHub website

1.  Sign in to GitHub.
2.  Click **New repository**.
3.  Choose a name such as `auroch-payment-channel-routing`.
4.  Choose Public or Private and create the repository.
5.  Select **Add file → Upload files**.
6.  Upload source files, `README.md`, `requirements.txt`, and
    `.gitignore`.
7.  Add a commit message such as `Initial Auroch implementation`.
8.  Click **Commit changes**.

### Option B --- Git commands

Open a terminal in the project root. Adjust filenames to match your
actual folder.

``` bash
git init
git add README.md .gitignore requirements.txt
git add rreq.py rrep.py auction.py bidding.py auction_result.py route_allocation.py payment.py
git add "liquidity(5).py"

git status
git commit -m "Initial Auroch implementation"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/auroch-payment-channel-routing.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username. If Git is already
initialized or a remote is configured, inspect first rather than
repeating setup commands:

``` bash
git status
git remote -v
```

For future updates:

``` bash
git add .
git status
git commit -m "Add Auroch experimental evaluation"
git push
```

Review `git status` before every commit to avoid uploading secrets,
large unwanted datasets, or temporary files.

## 9. Handover checklist

-   [ ] Latest end-to-end baseline simulation runs successfully.
-   [ ] Liquidity initialization method is justified and documented.
-   [ ] Exact paper experiment configuration is implemented.
-   [ ] 5,000 / 7,000 / 9,000 transaction experiments run.
-   [ ] 30× / 50× / 70× capacity experiments run.
-   [ ] Each configuration is averaged over 20 runs.
-   [ ] Success ratio is calculated and plotted.
-   [ ] Success volume is calculated and plotted.
-   [ ] Routing cost is calculated and plotted.
-   [ ] Raw and averaged results are saved.
-   [ ] Results are compared with the paper and limitations documented.
-   [ ] ECDSA is implemented and tested.
-   [ ] Dynamic `tau_fee` is implemented only after baseline evaluation.
-   [ ] Dynamic-fee experiments use the same configuration.
-   [ ] Baseline and dynamic-fee graphs are compared.

## 10. Handover note

The current code has a successful end-to-end **single-payment
simulation** and liquidity audit. Treat it as the working baseline, not
proof that every detail of the paper has been reproduced.

Preserve this baseline before major changes. Complete the
liquidity-method investigation and original paper experimental
evaluation first. Implement dynamic `tau_fee` only after the baseline
results and graphs are ready.
