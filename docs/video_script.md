# CampaignLift Demonstration Video Script

**Duration Target**: ~3 to 4 Minutes  
**Format**: Screen Recording with Voiceover  
**Presenter**: CampaignLift Team  

---

### [00:00 – 00:30] Scene 1: The Core Question

**Visual**: Camera on presenter, then cut to slide/title screen: *"CampaignLift: Stop Paying for Transactions You Were Already Going to Get"*.

**Voiceover**:  
> "Every marketing manager in Mobile Financial Services asks the same question: *'Which customers are most likely to transact if we send them a cashback offer?'*  
> But that is the wrong question. When you target by response probability, you spend your budget incentivizing 'Sure Things'—customers who would have paid anyway.  
> CampaignLift asks the true incremental question: *'Which customer transactions will happen ONLY IF we spend this incentive?'* Let's see how it works in practice."

---

### [00:30 – 01:10] Scene 2: Campaign Setup & Scenario Definition

**Visual**: Screen recording of `http://localhost/` -> Navigate to **Campaign Setup** (`/campaigns/new`).  
Fill out the form:
- Campaign Name: `Q4 Persuadables Growth Drive`
- Objective: `Activation`
- Offer Type: `Flat Cashback`
- Incentive Unit Cost: `50 BDT`
- Total Budget: `2,500 BDT`
- Click **Save & Continue to Scoring**.

**Voiceover**:  
> "Here in Campaign Setup, we define a new activation campaign with a 50 BDT cashback incentive and a 2,500 BDT budget.  
> Notice that we never upload customer CSVs. The system operates on pre-validated, governed customer cohorts to prevent data leakage and privacy contamination.  
> With one click, we trigger the causal inference engine."

---

### [01:10 – 01:50] Scene 3: Uplift vs. Response & Audience Insights

**Visual**: Navigate to **Audience Explorer** (`/audience`) and **Uplift Analysis** (`/uplift`).  
Show the customer table sorted by `Response Rank` vs `Uplift Rank`.  
Highlight the decile distribution SVG chart showing treatment vs. control conversion rates.

**Voiceover**:  
> "Our production LightGBM S-Learner estimates both counterfactual states for every customer: their probability of transacting with the offer, and their organic probability without it.  
> The difference is their incremental uplift.  
> In the decile chart, you can clearly see that the top 10% of customers deliver an 18.7% incremental lift. Further down, treatment and control curves converge—and in the bottom deciles, treatment actually causes negative reactions due to campaign fatigue."

---

### [01:50 – 02:40] Scene 4: Customer Explanation — The Causal Divergence

**Visual**: Click on customer `C00000170` to open the **Customer Explanation Drawer** (`/customers/C00000170`).  
Show the waterfall chart:
- $P(\text{control}) = 0.6509$
- $P(\text{treat}) = 0.7532$
- Uplift = $+0.1023$ (+10.23%)
- Reason Code: `incremental_candidate`
- Top features: `campaign_exposures_prior_90d (+0.15)`, `txn_count_90d (+0.12)`.  
Then contrast with a high-response 'Sure Thing' customer (`C00000012`, high organic rate, near-zero uplift).

**Voiceover**:  
> "Here is the heart of causal decision support. Look at customer `C00000170`.  
> A traditional response model ranked them 19th—overlooking them in favor of customers with 90% organic rates.  
> But CampaignLift ranks them Number 1 in incremental uplift, with an estimated +10.2% causal gain.  
> The explanation drawer explains why: they have high historical activity, but low recent exposure fatigue. They are a classic 'Persuadable'.  
> Meanwhile, customers with higher baseline transaction rates are flagged as 'likely_without_offer'—saving marketing budget."

---

### [02:40 – 03:15] Scene 5: Strategy Comparison & Budget Allocation

**Visual**: Navigate to **Strategy Comparison** (`/comparison`) and **Budget Optimization** (`/optimize`).  
Show the comparison matrix:
- Random Strategy: 44% negative uplift share
- Response Strategy: 40% negative uplift share
- Uplift Strategy: 0.0% negative uplift share, maximizing net transactions.

**Voiceover**:  
> "In the Strategy Comparison matrix, we compare all three targeting approaches under the exact same 2,500 BDT budget.  
> The standard response model wastes 40% of its budget targeting customers with negative uplift—customers who actually transact less when over-messaged.  
> CampaignLift's greedy knapsack optimizer excludes negative uplift completely, maximizing verified incremental value."

---

### [03:15 – 03:45] Scene 6: Grounded Gemini Copilot & Experiment Intelligence

**Visual**: Navigate to **Campaign Copilot** (`/copilot`).  
Type: *"Why was customer C00000170 prioritized over sure-thing customers?"*  
Show the instant response and the list of verified context fields used.  
Briefly show **Experiment Intelligence** (`/experiment`) showing the 30/30 sample support rule in action.

**Voiceover**:  
> "To assist campaign managers, our Campaign Copilot integrates Google Gemini.  
> But notice: the assistant is strictly grounded. It is hardcoded to answer exclusively from the verified run JSON, quoting exact numbers and refusing to hallucinate metrics or ROI.  
> In the Experiment Intelligence tab, simulated A/B trial slices enforce a strict 30-sample support threshold before reporting conversion rates, preventing statistical noise."

---

### [03:45 – 04:00] Scene 7: Human Oversight & Summary

**Visual**: Return to main Overview screen, pointing at the top-bar badge: `"Decision support"`.

**Voiceover**:  
> "Most importantly: CampaignLift is human-in-the-loop decision support. The system never sends campaigns or disburses funds automatically. The marketing manager makes the final commercial call.  
> By treating the persuadables and leaving the sure things alone, CampaignLift brings rigorous causal AI to growth marketing. Thank you."
