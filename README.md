# Ammonia Techno-economic model demo

An interactive Streamlit teaching app for undergraduate chemical engineering students. It connects material balances in a simplified ammonia synthesis loop to screening-level techno-economic analysis (TEA), with emphasis on the tradeoff between purge losses, recycle flow, and inert accumulation.

The app models fresh H₂/N₂ feed with a small argon impurity, fresh-feed compression, recycle mixing, a fixed-conversion reactor, complete ammonia removal, a purge/recycle split, and recycle recompression. It includes a live process-flow diagram, component stream tables, a production-cost waterfall, a configurable input-output sensitivity plot, and visible balance checks.

## Install and run

The project uses Python 3.11 or newer and [`uv`](https://docs.astral.sh/uv/).

```powershell
cd ammonia-demo
uv sync --dev
uv run streamlit run app.py
```

Open the local address printed by Streamlit, normally <http://localhost:8501>.

Run the automated checks with:

```powershell
uv run pytest
```

## Learning goals

Students can use the app to:

- close component, elemental, and mass balances around a recycle process;
- explain why an inert requires a purge at steady state;
- connect lower purge to lower reactant loss and higher recycle/inert loading;
- distinguish a specified single-pass conversion from a conversion predicted by thermodynamics or kinetics;
- identify which assumptions change material flows and which change only cost.

## Material-balance model

The sole reaction is:

```text
N₂ + 3 H₂ → 2 NH₃
```

All internal flows use kmol/h. The fixed continuous operating basis is represented symbolically in the displayed production formula:

```text
NH₃ kmol/h = annual NH₃ mass / MW_NH₃ / H_annual
```

For specified single-pass N₂ conversion `X` and purge fraction `p`:

```text
reaction extent       = NH₃ / 2
N₂ reactor inlet      = reaction extent / X
H₂ reactor inlet      = 3 × N₂ reactor inlet
N₂ fresh              = N₂ reactor inlet × [X + p(1 − X)]
H₂ fresh              = 3 × N₂ fresh
Ar fresh              = 4 × y_Ar,fresh × N₂ fresh / (1 − y_Ar,fresh)
Ar reactor inlet      = Ar fresh / p                    (p > 0)
```

`y_Ar,fresh` is the argon mole fraction of the total fresh H₂ + N₂ + Ar stream. `p` is the fraction of separator off-gas removed as purge before the remainder is recycled. The 3:1 fresh H₂:N₂ molar ratio preserves stoichiometry.

A positive argon feed with zero purge has no finite steady state and is reported as infeasible. When both fresh argon and purge are zero, the model selects the physically simple zero-argon loop inventory. Denominators are not clipped.

The reactor conversion is a user input. The app does not calculate conversion from temperature, pressure, equilibrium, reaction kinetics, catalyst performance, or inert dilution. Pressure controls affect compression duty only.

Complete ammonia removal is assumed. H₂, N₂, and Ar remain in the separator off-gas; each is split in the same purge/recycle proportion.

## Economic model

The reported metric is annualized production cost in USD per tonne of separated NH₃ at the plant gate. It includes:

- purchased H₂ and N₂;
- fresh-feed and recycle compressor electricity;
- an assumed specific cooling/refrigeration duty;
- annualized capital.

The fresh compressor raises total fresh gas from its supply pressure to loop pressure. The recycle compressor restores only the specified loop pressure drop. Both use the ideal-gas adiabatic equation:

```text
W = ṅ × [γ/(γ−1)] × R × T × [(P₂/P₁)^((γ−1)/γ) − 1] / η
```

The screening calculation uses a constant heat-capacity ratio, one isentropic efficiency, no intercooling, and no mechanical-drive losses. Compressor electricity and refrigeration electricity are separate cost lines; refrigeration electricity is not included again in compressor electricity.

Cooling is calculated from an explicitly labeled specific thermal duty and refrigeration coefficient of performance. It is an illustrative allowance, not a heat balance.

Equipment costs use:

```text
cost = reference cost × (current size / reference size) ^ scaling exponent
```

Fresh compressor, recycle compressor, reactor loop, cooler/gas separator, and ammonia separator are scaled separately. Reference equipment costs, sizes, exponents, nitrogen price, and cooling duty are illustrative teaching assumptions rather than validated plant estimates.

Capital is annualized with a simple straight-line teaching assumption:

```text
annualized capital = total installed capital / plant life
```

No discount rate or financing model is applied.

## Default scenario

| Input | Default |
|---|---:|
| Single-pass N₂ conversion | 20% |
| Purge fraction | 5% |
| Argon in total fresh feed | 0.5 mol% |
| Annual NH₃ production | 100,000 t/y |
| Operating basis | Continuous, 8,760 h/y |
| Purchased H₂ | $2.00/kg |
| Purchased N₂ | $50/t |
| Electricity | $0.0862/kWh |
| Fresh-feed / loop pressure | 30 / 150 bar |
| Loop pressure drop | 5 bar |
| Compressor efficiency | 75% |
| Cooling duty / COP | 0.80 kWh-thermal/kg NH₃ / 3.0 |
| Plant life | 20 years |

The operating basis is fixed rather than exposed as a teaching input.

## Product boundary and exclusions

The product is completely separated NH₃ at the plant gate. Fixed operating costs, storage, transport, taxes, subsidies, working capital, catalyst replacement, reaction heat recovery, and detailed utility systems are excluded. Upstream H₂ and N₂ production equipment and emissions are excluded; their effects enter only through purchased feed prices. No temperature or pressure dependence of conversion is modeled.

The results are suitable for teaching trends and checking balances. They are not suitable for plant design, investment decisions, safety analysis, or predicting achievable conversion.

## Sources

- Molecular and atomic weights: [NIST Chemistry WebBook — hydrogen](https://webbook.nist.gov/cgi/cbook.cgi?Name=H2) and [NIST Atomic Weights and Isotopic Compositions](https://pml.nist.gov/cgi-bin/Compositions/stand_alone.pl).
- Default electricity price: [U.S. Energy Information Administration, 2025 U.S. industrial average retail electricity price of 8.62 cents/kWh](https://www.eia.gov/energyexplained/electricity/prices-and-factors-affecting-prices.php).
- TEA methodology context: [U.S. Department of Energy H2A Production Analysis](https://www.energy.gov/eere/h2awsm/techno-economic-analysis-hydrogen-production). H2A is cited as an example of transparent, consistent TEA reporting; this app does not model upstream hydrogen production.

## Project structure

```text
app.py                          Streamlit interface
ammonia_teaching/model.py       Pure stream and balance calculations
ammonia_teaching/economics.py   Compression, capital, and annualized costs
ammonia_teaching/sensitivity.py One-variable sensitivity sweeps
ammonia_teaching/charts.py      Plotly figures
tests/                          Balance, limiting-case, trend, and finance tests
```
