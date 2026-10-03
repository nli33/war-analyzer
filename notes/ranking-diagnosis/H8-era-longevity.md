# H8: era cohorts and longevity

Ranked population: 343 generals across 7 era cohorts. Part 1 compares the shipped per-era z-scoring against a single global cohort; part 2 compares `longevity_adjusted_value` (wins per career year) against `win_rate` (wins per battle, already shipped in `war/metrics/rate.py`).

## Part 1: era cohorts

### Cohort sizes

0 singleton-era cohort(s), 0 two-person-era cohort(s) -- the smallest cohort today is Modern at 12 generals. `war/metrics/composite.py`'s own docstring flags a zero-variance (singleton-cohort) convention as a live concern for "this 8-general roster" (four of its eight generals were the sole representative of their era, forcing `z = 0.0` and a composite score of exactly 0 for each). That was true for the locked tonight-only demo roster the docstring describes; it is no longer true for the real 343-general pipeline roster -- H1's date fixes and H4's row-recovery fixes grew every era past the singleton/pair danger zone entirely. Worth updating that docstring (flagged for H9) since it now describes a problem that doesn't exist in the data it ships against, even though the convention itself (z = 0.0 on zero variance) is still correct code to keep for whatever cohort eventually does thin out again.

An algebraic version of the same mechanism still holds at any size, though: with only two cohort members, population z-scoring assigns z = +1/-1 to whichever value is larger (or z = 0 if they tie) no matter how big the gap is -- for values a != b, mean = (a+b)/2 and population std = \|a-b\|/2, so z = (a-mean)/std = sign(a-b) * 1 always. A one-point OAR gap and a 500-point OAR gap in a two-person era would produce an identical z. The smallest real cohort today (12 generals) is far enough from that extreme that it doesn't happen in practice -- and, measured directly rather than assumed, cohort size turns out **not** to predict how extreme a cohort's z-scores get once it's above a dozen members: Spearman correlation between era size and mean \|z\| across the 7 eras is -0.180, and size vs. max \|z\| is +0.591 -- if anything the largest cohort (Early Modern, 107) has the single most extreme z-score in the whole ranking, not the smallest one, because a bigger pool gives one real outlier more room to separate from a tighter-packed mean/std rather than less. The two-member mechanical stretch is a genuine edge case worth keeping in mind if a future roster change ever shrinks a cohort back down near it, but it is not today's shape of the problem.

| Era | Generals | Mean \|z\| (OAR/WAR-residual/longevity, pooled) | Max \|z\| |
|---|---|---|---|
| Modern | 12 | 0.796 | 2.354 |
| Ancient | 18 | 0.842 | 2.206 |
| Medieval | 23 | 0.694 | 4.587 |
| WWII | 37 | 0.767 | 4.522 |
| Industrial | 73 | 0.825 | 2.652 |
| Napoleonic | 73 | 0.769 | 4.793 |
| Early Modern | 107 | 0.734 | 5.581 |

### Global z-score vs. per-era z-score

Spearman rank correlation between the shipped per-era ranking and the same four inputs z-scored once over the whole ranked population instead: +0.989. Top 30: 3 enter under global z-scoring that aren't in the per-era top 30 (Charles John, Radomir Putnik, Mustafa Kemal), 3 leave (Han Xin, Stilicho, Cardinal-Infante Ferdinand).

Reference-list agreement (mean Spearman across 4 sources, same resolution H3/H6/H7 reuse, zero new network calls): per-era (shipped) = +0.363, global = +0.332.

Must-include generals, rank under each cohort scheme:

| General | Per-era rank | Global rank | Delta |
|---|---|---|---|
| Julius Caesar | 77 | 80 | +3 |
| Alexander the Great | 9 | 20 | +11 |
| Temujin | 130 | 128 | -2 |
| Saladin | 257 | 268 | +11 |
| Frederick the Great | 100 | 101 | +1 |
| Napoleon I | 12 | 11 | -1 |
| Ulysses S. Grant | 20 | 18 | -2 |
| Georgy Zhukov | 16 | 4 | -12 |
| Hannibal | 147 | 122 | -25 |
| Scipio Africanus | 34 | 42 | +8 |
| Subutai | 21 | 3 | -18 |
| Matsudaira Motoyasu | 142 | 140 | -2 |
| George Washington | 174 | 166 | -8 |
| Arthur Wellesley | 78 | 69 | -9 |
| Robert E. Lee | 179 | 183 | +4 |
| Dwight D. Eisenhower | 7 | 1 | -6 |
| Erwin Rommel | 273 | 272 | -1 |
| Erich von Manstein | 172 | 165 | -7 |
| Douglas MacArthur | 157 | 198 | +41 |
| Han Xin | 14 | 33 | +19 |

## Part 2: longevity alternatives

70 of 343 ranked generals have `longevity_adjusted_value` > 1.0 -- impossible for any *rate* metric bounded in [0, 1] like `win_rate`, since it is a per-year *sum* of up-to-1.0 outcome scores, not an average. A general who fights several battles within one career year and wins them all scores above the single-battle maximum.

Top 10 by `longevity_adjusted_value`:

| General | Longevity-adj. value | Career value | Career years | Battles | Win rate | Rank (longevity) | Rank (win_rate swapped in) |
|---|---|---|---|---|---|---|---|
| Edmund Allenby | 7.500 | 15.0 | 2 | 16 | 0.94 | 1 | 8 |
| Abdul Fatah Younis | 6.000 | 6.0 | 1 | 9 | 0.56 | 13 | 50 |
| Rochejaquelein | 6.000 | 6.0 | 1 | 9 | 0.67 | 31 | 135 |
| Lee Kwon Mu | 5.000 | 5.0 | 1 | 5 | 1.00 | 3 | 3 |
| Carl Johan Adlercreutz | 5.000 | 5.0 | 1 | 5 | 1.00 | 11 | 38 |
| Pietro Badoglio | 4.500 | 4.5 | 1 | 5 | 0.80 | 30 | 70 |
| Charles X Gustav | 4.000 | 8.0 | 2 | 10 | 0.80 | 6 | 56 |
| José de Urrea | 4.000 | 4.0 | 1 | 4 | 1.00 | 18 | 45 |
| Oku Yasukata | 4.000 | 4.0 | 1 | 4 | 1.00 | 19 | 46 |
| Ramón Blanco | 4.000 | 4.0 | 1 | 6 | 0.67 | 72 | 133 |

Swapping `win_rate` in for `longevity_adjusted_value` as the composite's fourth input (same weight, same era z-scoring, only the raw value changes) moves the full ranking: Spearman vs. the shipped ranking = +0.983. The effect is concentrated exactly where the tiny-career theory predicts it: every one of the top 10 longevity generals above has a 1- or 2-year career and well under 20 battles, and every one drops under the win_rate swap (Allenby 1 -> 8, Abdul Fatah Younis 13 -> 50, Rochejaquelein 31 -> 135, Adlercreutz 11 -> 38) because win_rate has no time dimension to reward a short career for compressing its wins into fewer years. **Answer to this task's question: yes, wins-per-career-year still rewards tiny careers after H1's date fix** -- H1 fixed *which* years a career spans, not the shape of dividing a bounded sum by an unbounded-small denominator, which is a method property of the metric, not a data bug.

The third alternative PROGRESS.md names, career span from Wikidata birth/death years, is not computed here -- see this script's module docstring for why (no cached source for it, and Phase H's rules hold to zero new network calls this run even though a batched Wikidata query would likely be cheap). Flagged for a future ingestion task, not this diagnosis phase.

