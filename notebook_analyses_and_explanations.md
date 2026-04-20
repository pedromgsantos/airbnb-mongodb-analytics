# BDMM Notebook Analyses and Explanations

This file contains the markdown narrative extracted from the original notebook, including assumptions, interpretation, analysis, and conclusions.

--- CELL 1 ---
# Homework: Airbnb Database Analysis
## Group members:
1. `Part A: 20250448 | João Paulo de Avila`
2. `Part B: 20250448 | Lucas Campos Ferreira`
3. `Part C: Student number | Full name`
4. `Part D: 20250399 | Pedro Miguel Gaspar Santos`
5. `Part E: 20250418 | Pedro Miguel Gonçalves Fernandes`



--- CELL 2 ---
## Setup and Connection

Connect to the MongoDB instance (tries Tailscale VPN first, falls back to localhost) and select the `sample_airbnb` database.

--- CELL 4 ---
## Variables

All constants and configuration values used across the notebook, grouped by task.


--- CELL 6 ---
# Functions

Shared utilities used across all tasks: index management (hide/unhide for explain comparisons), explain comparison pipeline, and plotting helpers.

--- CELL 8 ---
## Loading Source Data

List available collections, select the source, and save sample documents for inspection.

--- CELL 11 ---
## Data Errors & Cleaning

Exploration and correction of data quality issues in the source collection, applied **before** splitting into target collections. The source collection `listingsAndReviews_HW2_new` is **never modified** - all fixes are applied during copy into `listingsAndReviews_HW2_clean`.

--- CELL 14 ---
# Inspection and Cleaning

The original collection stores everything in a single document. We apply a **hybrid embedding/referencing** strategy: fields that are read together and bounded in size stay **embedded**, while unbounded arrays, rarely-needed data, and entities reused across listings are **referenced** in separate collections.

<details>
<summary><b>Collection Design (Embedding vs. Referencing)</b></summary>
<br>

**`listings`** - **Main analytical entity**. Embeds host snapshot, address, amenities, review scores, availability, and pricing.
- 1-to-1 sub-documents and bounded arrays, always queried together. Embedding avoids `$lookup` overhead in the analytical pipelines.
- Persisted **computed fields** added during the split: `host_type`, `price_ppn_2g`, `price_ppn_3g`, `popularity_score`, `size_category`, `number_of_reviews`, plus a `reviews_subset` array with the 5 most recent reviews (Subset Pattern).

**`reviews`** - **Referenced**, one document per review linked by `listing_id`.
- 1-to-N unbounded. Reviews grow over time; referencing allows independent growth without hitting the 16 MB document size limit and preserves the full review history instead of overwriting it.

**`hosts`** - **Referenced**, one document per `host_id`. Built by aggregating all listings of each host during the split.
- N-to-1: many listings share one host. A separate collection avoids duplicating host-level data across every listing of the same host and is the natural unit of analysis for D2 (host features vs satisfaction).
- Stores precomputed binary features (`is_fast_responder`, `is_perfect_responder`, `is_flexible_cancellation`) and `avg_rating` across all listings of the host (Computed Pattern).
- Also embeds `host_name`, `host_location`, `host_since` inline (Extended Reference) so display queries do not need a second lookup.

**`listing_text`** - **Referenced**, text blobs keyed by `listing_id`.
- **Subset Pattern**: large text fields (`summary`, `description`, `notes`, etc.) are rarely needed for analytics. Keeps `listings` lean; text retrieved via `$lookup` when needed.

</details>

<details>
<summary><b>MongoDB Patterns Applied</b></summary>
<br>

- **Subset** -> `listing_text` split from `listings`, plus `reviews_subset` (5 most recent reviews) embedded inside each listing - keeps the frequently-queried collection small while still serving display queries without a join.
- **Extended Reference** -> `reviews` stores `reviewer_name` inline; `hosts` stores `host_name`, `host_location`, `host_since` inline - avoids extra lookups for display-ready data.
- **Computed** -> `review_scores` embedded in `listings` (pre-aggregated scores from individual reviews); `price_ppn_2g`, `price_ppn_3g`, `popularity_score`, `host_type`, `size_category`, `number_of_reviews` persisted on `listings`; `avg_rating` and the three binary host features (`is_fast_responder`, `is_perfect_responder`, `is_flexible_cancellation`) persisted on `hosts`. All values are computed once during the split and refreshed on demand, avoiding repeated work in analytical pipelines.
- **Attribute** -> `amenities` as a flat array in `listings` - flexible querying with a multikey index; bounded list.

</details>

<details>
<summary><b>Cleaning &amp; Split Strategy</b></summary>
<br>

- The source collection `listingsAndReviews_HW2_new` is **never modified**.
- All fixes are applied during copy into `listingsAndReviews_HW2_clean` (duplicates removed, names/fields defaulted, reviews deduplicated, ratings clipped, inverted review dates swapped, non-positive prices nulled, amenities normalised).
- The clean collection is then split into `listings`, `reviews`, `hosts`, and `listing_text`. All `Decimal128` values are converted to `float`/`int` during the split so downstream cells can use plain arithmetic.
- `review_scores_rating` (top-level) - redundant with `review_scores.review_scores_rating`, excluded from `listings`.

</details>

--- CELL 18 ---
## Pattern Motivation Analysis

Concrete, data-driven justification for every MongoDB pattern applied in the collection design. For each pattern, a measurement (document size comparison, timing, query plan) demonstrates **why** the pattern is beneficial.

--- CELL 20 ---
# Task A

--- CELL 21 ---
## A1 - Price Analysis
**Student:** 20250436 | Joao Paulo de Avila

This notebook analyzes **price per person per night** for five property types in **Hong Kong, Montreal, and Barcelona**.

The analysis assumes a stay of **3 people for 7 nights**.


--- CELL 22 ---
## Assumptions and decisions

- The analysis includes only the three requested cities: `Hong Kong`, `Montreal`, and `Barcelona`.
- The analysis includes only the five requested property types: `Apartment`, `Guesthouse`, `Hostel`, `House`, and `Townhouse`.
- Only listings with a valid nightly `price` were kept.
- `cleaning_fee` is added **once per stay**.
- `extra_people` is treated as a **per extra guest per night** fee.
- Missing fee values are treated as `0`, because the cleaned collection already standardizes missing fee fields.
- The formula used is:

`price_per_person_per_night = (price * 7 + cleaning_fee + extra_people * max(0, 3 - guests_included) * 7) / (3 * 7)`

- In the box plot, the line inside each box is the **median**, the box represents the **middle 50%** of values, and the whiskers show the **real minimum and maximum** prices.


--- CELL 26 ---
### Result analysis and interpretation

The chart shows a clear price gap between the three cities. Hong Kong is the most expensive market in almost every property type. Its median prices are much higher than those of Montreal and Barcelona, especially for apartments and houses. This suggests that even after splitting the total cost across three people and seven nights, accommodation in Hong Kong remains expensive.

Montreal and Barcelona are much closer to each other. For apartments, both cities have much lower median values than Hong Kong, although Montreal is slightly higher than Barcelona. Houses and townhouses in Montreal are also relatively expensive compared with its apartments, which may reflect larger spaces and more private use. In Barcelona, apartments dominate the sample and have a lower median, but the distribution still contains some high values, which indicates a few premium listings pushing the upper range upward.

Another important point is sample size. Apartments have many observations in all three cities, so their distributions are more reliable. Some other categories, such as guesthouses, hostels, and townhouses, have very few listings in some cities. Because of that, those box plots should be interpreted carefully. When a group is very small, one listing can strongly affect the minimum, maximum, and even the median.

The visual is aligned with the task requirements. Each group on the x-axis represents one of the five requested property types, and within each group the three cities are compared side by side. The median is shown by the line inside each box, the middle 50% of values is shown by the box, and the whiskers show the full observed minimum and maximum. This makes the chart easy to read and supports comparison between cities and property types in a single figure.

Overall, the main pattern is clear: Hong Kong is the premium market, while Montreal and Barcelona are more affordable for a group of three people staying one week. Apartments are the most common type and provide the clearest comparison. Houses and townhouses often show more variation, which suggests that property size, location, and extra fees can change the final per-person nightly cost substantially.


--- CELL 27 ---

## A2 - Query Pipeline Analysis

This section analyzes **New York** listings that include all of these amenities: `Wifi`, `Hair dryer`, `24-hour check-in`, `Air conditioning`, and `Bed linens`.

The analysis assumes a stay of **3 people for 7 nights**.


--- CELL 28 ---
## Assumptions and decisions

- I used the cleaned `listings` collection.
- Only New York listings with **all five required amenities** were included.
- A listing is **wheelchair-friendly** if it has at least one of these amenities: `Elevator`, `Ground floor access`, `Wheelchair accessible`, `Wide doorway`, `Disabled parking spot`.
- A listing is **family-friendly** if it has at least one of these amenities: `Crib`, `Family/kid friendly`, `Stair gates`, `Table corner guards`.
- A listing can belong to both categories if it satisfies both conditions.
- Price per person per night includes `price`, `cleaning_fee`, and `extra_people`.
- There is no separate `child_fee` field in this dataset, so no child fee was added.
- `security_deposit` was not included because it is refundable and not part of the effective accommodation cost.
- Formula used:

`price_per_person_per_night = (price * 7 + cleaning_fee + extra_people * max(0, 3 - guests_included) * 7) / (3 * 7)`


--- CELL 29 ---
### Step 1 - Build the query result

First, I create the subset for New York, calculate the price per person per night, and transform the result into a comparison table.


--- CELL 31 ---
### Step 2 - Check how many valid groups exist

This check is important because the task asks for five property types, but the filtered data may contain fewer valid groups.


--- CELL 33 ---
After applying the exact A2 filters, the final subset contains only **3 property types** with valid category results: `Apartment`, `House`, and `Townhouse`.

Because of that, the visual below shows all valid remaining property types in the filtered subset.


--- CELL 34 ---
### Step 3 - Create the A2 visual

The box plot compares wheelchair-friendly and family-friendly prices side by side for each available property type.


--- CELL 36 ---
### Step 4 - Compare query performance

Now I compare the before and after versions using `explain`, plus a real execution run for each pipeline.


--- CELL 38 ---
### Step 5 - Visual of Query Before and After

The charts below make the performance difference easier to read.


--- CELL 40 ---
### Result analysis and interpretation

After filtering New York listings to the five required amenities, only 30 listings remained. After applying the wheelchair-friendly and family-friendly rules, the final result produced 26 rows because some listings belong to both categories. Apartments dominate the filtered subset, so they are the most reliable comparison. Family-friendly apartments and wheelchair-friendly apartments have the same median price per person per night, about 56.33, but family-friendly apartments show a slightly higher average because a few listings are more expensive. The only other cases are one family-friendly house and one wheelchair-friendly townhouse, so those groups are too small to represent a stable market pattern.

The performance comparison shows that the after version is better for repeated use. The before query does a collection scan and examines all 5,553 listing documents. The after query starts with the New York and amenities filter and uses the compound index, reducing examined documents to 599 and lowering explain time to about 2 ms.


--- CELL 41 ---

## A3 - Analytical Price Suggestion

This section suggests prices for listings with missing `price` values and then analyzes only the suggested prices for **Hong Kong, Montreal, and Barcelona**.


--- CELL 42 ---
## Assumptions and decisions

- I used the cleaned `listings` collection.
- I suggested a **nightly price** for each listing with missing `price`.
- Similar properties were defined using a simple hierarchy: market, property type, room type, and accommodates.
- I used the **median** price of similar properties instead of the mean because median is more stable when there are expensive outliers.
- The matching order is: 1. same market + property type + room type + accommodates, 2. same market + property type + room type, 3. same market + property type, 4. same property type + room type, 5. same property type, 6. same market, 7. global median fallback.
- At least **3 donor listings** are required before using a comparison group.
- I updated the database by writing the new field `price_suggestion` to each listing with missing price.
- For the final graph, I used only listings where the original `price` was missing and the suggestion came from `price_suggestion`.
- Price per person per night was calculated with the same assumption as A1: **3 people for 7 nights**, including `cleaning_fee` and `extra_people`.
- Formula used for the final graph:

`price_per_person_per_night = (price_suggestion * 7 + cleaning_fee + extra_people * max(0, 3 - guests_included) * 7) / (3 * 7)`



--- CELL 43 ---
## Step 1 - Build reference prices from similar listings

First, I collect listings that already have a real price. These listings will be the reference group used to estimate missing prices.


--- CELL 45 ---
## Step 2 - Suggest prices for listings with missing price

The code below checks each missing-price listing against the similarity hierarchy and chooses the median price from the first valid donor group.


--- CELL 48 ---
## Step 3 - Keep only suggested prices for the final A3 graph

Now I select only listings that originally had missing `price`, already received `price_suggestion`, and belong to the required cities and property types for the final visual.


--- CELL 50 ---
## Step 4 - Create the A3 visual

The graph below uses only the suggested prices and groups the 15 box plots by property type, with the three cities shown side by side.


--- CELL 52 ---
## Result analysis and interpretation

The price suggestion method worked well for this dataset because it used a simple but practical similarity hierarchy. Most missing-price listings received a suggestion from the most specific level, which means many listings had a strong reference group with the same market, property type, room type, and accommodates value. This is useful because it keeps the suggestion close to the local market and to the expected guest profile. Only a small number of listings needed broader fallback rules such as same market or same property type.

Looking only at suggested prices in Hong Kong, Montreal, and Barcelona, the same broad pattern from A1 appears again. Hong Kong tends to have the highest suggested price per person per night, especially for apartments and houses, while Montreal and Barcelona stay lower. Apartments dominate the dataset and therefore give the most stable distributions. Guesthouses, hostels, houses, and townhouses appear less often among missing-price listings, so those box plots should be interpreted more carefully because small samples can make the spread look unstable. In some property type and city combinations, the number of suggested-price listings is very small, so the box plot may collapse into a short box or almost a line.

Another strength of this approach is that the result is operational, not just analytical. Each missing-price listing now has a `price_suggestion` value written back to the database, which means the output can be reused later without repeating the full manual comparison process. This also keeps a clear record of how each suggestion was produced, because the notebook stores the matching rule and donor count used for the estimate.

Overall, the approach is simple and defendable: use the median price of the most similar available listings, write the suggestion back to the database, and then compare the suggested prices across cities and property types. This gives hosts a clear reference value without using a complex model, while still respecting local market differences and basic property characteristics.


--- CELL 53 ---
# Task B - Rating Analytics Expert

--- CELL 54 ---
## Setup and Connection

Connect to the MongoDB instance (tries Tailscale VPN first, falls back to localhost) and select the `sample_airbnb` database.

--- CELL 55 ---
## B1. Score Analysis

<details>
<summary><b>Assumptions & Decisions</b></summary>
<br>

- **Cities filtered by** `address.market` matching exactly `"Hong Kong"`, `"Montreal"`, `"Barcelona"`.
- **Rating fields** live inside the embedded `review_scores` sub-document (e.g. `review_scores.review_scores_cleanliness`). Scale is 0–10.
- **Missing scores**: properties with no `review_scores` or where a specific sub-score is `null`/missing are **excluded** from that category - they have never been rated, so including them would distort the distribution.
- **Outliers** shown as individual points beyond 1.5 × IQR.

</details>

--- CELL 58 ---
### B1 - Interpretation

Looking at the 15 box plots, the first thing that jumps out is how top-heavy these scores are. Most medians sit at 10 (the ceiling of the scale), which compresses the boxes into narrow bands and pushes anything below 8 into outlier territory.

**Communication** is the most uniformly high category - all three cities cluster tightly around 9–10 with very little spread. Hosts generally do well here regardless of market.

**Location** is also rated high overall, but Barcelona has a noticeably tighter distribution than Hong Kong or Montreal. This makes sense: Barcelona’s Airbnb supply is concentrated in the city centre (Eixample, Gothic Quarter), so most guests end up in walkable tourist areas. Hong Kong, on the other hand, has listings scattered across Hong Kong Island, Kowloon, and the New Territories - some of those locations are far less convenient, which explains the wider spread.

**Cleanliness** and **Accuracy** behave similarly across cities, with medians around 9–10. However, both categories show outliers dropping as low as 2–4 in all three markets. These represent a small but notable group of properties that fall well below expectations, potentially due to misleading photos or poor upkeep. From a business perspective, these listings are candidates for review or delisting.

**Value** is where things get interesting - it is the lowest-rated and most variable category. The median drops to 9, and the IQR is visibly wider than in other categories. Hong Kong scores slightly lower on value, which aligns with its high cost of living; guests paying premium prices may feel they are getting less for their money. Montreal sits at the other end, with a tighter and slightly higher distribution, consistent with it being a more budget-friendly destination.

In short, guests rate communication and location consistently well, but value perception varies the most - both between and within cities. For hosts, improving value perception (better pricing, more amenities for the price) is probably the highest-impact lever for boosting overall ratings.

--- CELL 59 ---
## B2. Review Quality and Activity Score

<details>
<summary><b>Assumptions & Decisions</b></summary>
<br>

- **City**: `address.market == "New York"`. Only properties with `number_of_reviews ≥ 10` and a non-null `review_scores.review_scores_rating` are included.
- **Rating normalisation**: `review_scores_rating` is on a 0–100 scale. We divide by 100 to bring it to 0–1 so all three score components are comparable before weighting.
- **Normalised review count**: `number_of_reviews / max(number_of_reviews)` computed **within each property type group** (e.g. Apartment max is independent of House max).
- **Recency score**: For each property, `days_gap = (global_latest_review_date − property_latest_review_date)`. Then `recency = 1 − days_gap / max(days_gap)`. The property with the most recent last-review gets 1; the one with the oldest gets 0. The global latest date comes from the entire `reviews` collection.
- **Latest review date** is obtained via `$lookup` from the `reviews` collection (sorted by date desc, limit 1), leveraging `idx_listing_date`.
- **Weekly recalibration**: the score is written back to each listing document as `quality_activity_score` using `bulk_write`, so downstream queries can read it directly without recomputing. An index on `(address.market, quality_activity_score)` supports fast retrieval.
- **Property types with very few listings** (1–2) will still appear in the comparison table but produce thin box plots - this is expected given the data.

</details>

--- CELL 63 ---
### B2 - Interpretation

**Score distribution**: Apartments dominate the dataset (295 of 384 properties) and show the widest spread in scores (roughly 0.43–0.96), with a median around 0.70. Smaller property types like Guesthouse and Guest suite score higher on average, likely because hosts with niche listings tend to be more attentive and receive reviews more frequently. Types with just 1–2 listings (Aparthotel, Other, Villa) are not statistically meaningful.

The score is heavily driven by the rating component (0.5 weight) - since most ratings cluster near 90–100, the main differentiators are review count and recency. Properties that are both active and well-reviewed rise to the top.

**Query performance**: Without indexes, the naive pipeline did a full collection scan and the `$lookup` pulled every review per listing into memory, examining over 57 million documents and taking 15+ seconds. The optimised version combines two improvements: (1) the compound index `idx_market_nreviews` lets the `$match` stage use an IXSCAN, dropping docs examined from 57M to 384, and (2) the sub-pipeline `$lookup` with `$sort` + `$limit 1` uses `idx_listing_date` to fetch only the latest review per listing instead of all of them. Together this brings execution from ~15s to ~60ms. Writing the score back to each listing avoids recomputation for downstream reads.

--- CELL 64 ---
## B3. Long-Term Rental Suggestion

<details>
<summary><b>Assumptions & Decisions</b></summary>
<br>

- **Cities**: `address.market` in `["Hong Kong", "Montreal", "Barcelona"]`.
- **Review as occupancy proxy**: a review in a given month means the property was occupied that month. Months with zero reviews are treated as vacant.
- **Per-year analysis**: for each property, vacancy is computed separately per calendar year. Only years where the property has at least one review are considered (otherwise we have no signal).
- **Averaging across years**: for each month, we compute the fraction of years in which that month had zero reviews. A month is flagged as “vacant” if it was empty in more than half of the years with data (vacancy rate > 0.5).
- **Consecutive-month rule**: a long-term rental suggestion is made only when two or more consecutive vacant months appear. Isolated single vacant months are ignored - they may just reflect seasonal dips rather than true vacancy. December and January are treated as consecutive (year wrap-around), so a vacancy pattern that spans the turn of the year (e.g. November–February) is detected as one continuous run rather than two separate ones.
- **`rental_suggestion` field**: written back to each listing as an array of month numbers (1–12). Properties with no suggestion get an empty array.
- **Yearly update**: the query is designed to run once a year. The `rental_suggestion` field is overwritten each time via `bulk_write`.

</details>

--- CELL 67 ---
### B3 - Interpretation

The scatter plot reveals distinct seasonal vacancy patterns across the three cities, and therefore different windows where hosts should consider long-term rentals.

**Montreal** consistently has the highest number of properties flagged for long-term rental, peaking at around 415 in April and staying above 300 for most of the year. The dip to ~227 in August aligns with Montreal’s short summer season - July and August are prime tourist months, so properties are actually occupied and fewer show recurring vacancy. The rest of the year, especially the long winter months (November through April), shows high vacancy, suggesting many hosts struggle to fill their listings outside of summer. This makes Montreal an ideal market for winter long-term rental conversions.

**Hong Kong** follows a different pattern. Vacancy suggestions peak from March to July (300–336 properties), then drop steadily toward December (178). The low point in winter (January ~129) likely reflects Chinese New Year and local holiday travel boosting short-term demand. The mid-year peak is harder to explain by tourism alone - it may reflect a period where Hong Kong hosts face competition from hotels or where the monsoon/typhoon season discourages short stays.

**Barcelona** has by far the fewest rental suggestions (73–141 per month), with a clear trough from June to August (~73–90 properties). This is expected: Barcelona is one of Europe’s top summer destinations, so almost all listings see tenant activity during those months. The slight uptick in November–February (~117–141) suggests a mild winter vacancy window, but the numbers are much lower than the other two cities. Barcelona’s year-round appeal as a tourist destination means fewer properties sit truly empty.

Overall, Montreal hosts have the most to gain from long-term rental conversion - particularly during winter. Hong Kong hosts should consider mid-year options, while Barcelona hosts have relatively little recurring vacancy to exploit.

--- CELL 68 ---
# Task D

--- CELL 69 ---
---

#### D1. Host Type and Pricing

Compares the price per person per night between professional hosts (more than one listing in our database) and amateur hosts (exactly one listing) across Hong Kong, Montreal and Barcelona.

**Assumptions**

- Price per person per night is read from the precomputed `price_ppn_2g` field built during the common modelling step. The formula assumes 2 guests staying 7 nights and includes the cleaning fee (charged once per stay) and the extra-person fee for any guest above `guests_included`. Detailed formula is documented in the split cell.
- Listings with `price_ppn_2g` set to null are excluded from the analysis. These are the 1681 listings (30.3% of the dataset) that the source has with null `price`. Imputation of these prices is the responsibility of task A3; rerunning D1 against the imputed dataset would require only swapping the `$match` filter.
- Host classification uses the `host_type` field built during the common modelling step. The classification is based on the actual count of listings per `host_id` in our database, not on the source field `host.host_listings_count`, which refers to the host's global Airbnb count and does not match what is in our extract.
- Box plots use the seaborn default whisker rule (1.5 × IQR). Listings outside the whiskers are shown as outlier dots.
- For visualization purposes, listings priced above the 95th percentile of their own city are dropped. This removes a small number of extreme outliers (notably one Hong Kong listing at 5000 USD per night) that would flatten the box plots and prevent visual comparison. The descriptive statistics table reports both the raw and the clipped distributions; the interpretation in the report uses the raw distribution.

--- CELL 75 ---
#### Key findings

- **Hong Kong is in a different price tier.** Median price per person per night is roughly 5 to 10 times higher than Montreal and Barcelona regardless of host type.
- **Headline numbers go in opposite directions.** In Hong Kong, amateurs are more expensive than professionals (median 343 vs 224 USD). In Montreal and Barcelona it is the opposite (Montreal 39.5 vs 52.7 USD, Barcelona 30 vs 51.1 USD).
- **The Hong Kong inversion is composition, not behaviour.** Hong Kong professionals are 66% private rooms vs 39% for amateurs; Montreal and Barcelona professionals are 94% and 88% entire-home listings vs 67% and 41% for amateurs. Different host types specialise in different room types in different markets.
- **When room type is held constant, the professional premium is consistent and modest.** Looking only at Entire home/apt listings: Barcelona professionals are 13% more expensive, Montreal 11% more expensive, Hong Kong 6% less expensive (with only 37 professional listings, on the edge of statistical noise). The real "professional premium" is therefore around 10%, not as was expected.
- **Amateurs show much higher price variability than professionals.** The interquartile range of amateur listings is roughly twice that of professionals in all three cities. Professionals standardise pricing; amateurs price each listing individually.
- **Extreme outliers cluster on the amateur side.** The top end of the dataset (one Hong Kong listing at 5000 USD per night, one Barcelona listing at 1500 USD per night for professionals and 1000 USD for amateurs) is dominated by single-property hosts running niche luxury listings.
- **Sample sizes are sufficient.** All six (city, host_type) groups have at least 47 listings, enough to support these conclusions, with the caveat that the controlled comparison for Hong Kong professional Entire home/apt has only 37 listings.
- **30% of the dataset has no price** and was excluded from this analysis. Once task A3 imputes these prices, rerunning D1 against the enriched dataset is a one-line filter change.

---

--- CELL 76 ---
**D2. Host Features Impact on Satisfaction**

The goal is to test the hypothesis that certain host features have a direct impact on customer satisfaction (measured by review score). Specifically, consider the following host features: Superhost status (host_is_superhost), Response time (host_response_time), Host verification status (host_is_verified), Cancellation policy (cancellation_policy), Response rate (host_response_rate).

Customer satisfaction is measured using the review score (review_scores_rating). If the host manages multiple properties, take the average score across listings. Since not all attributes have numerical binary value type, you would need to represent the meaning in strings into relative scores, and choose how to make a split of values into binary. E.g. response time should be translated into whether or not the host is a fast-responder, or not.  

Satisfaction difference score based on each of host features: For each feature (superhost status, response time, etc.) calculate the score. You could calculate using the following example: 

Satisfaction difference = Average Satisfaction for Superhosts - Average Satisfaction for Non-Superhosts

You can add a weight to adjust the score calculation. In which case, make sure to state that in the assumptions. 

Create a double lollipop chart for each host attribute considered in the task. Visualise the difference in the score per attribute. X-axis should hold attributes, y-axis should hold the (weighted) score, and double lollipop stands for each binary value.

Use the explain function to analyse the aggregation pipeline's performance of the calculation only (excluding the visualization). Evaluate which query structures, stages, array handing approaches, patterns, indexes, and other approaches improve execution efficiency. Produce a comparison table with metrics such as execution time, documents examined, keys examined, stage type, and memory usage for before and after the improvements in query performance that you introduced.

The delivered assignment should have three components: 1. assumptions and decisions. 2. a lollipop chart with 5 host attributes and their scores. 3. comparison table of query performance before and after optimization. 4. interpretation of results (max 200 words).

--- CELL 77 ---
---

#### D2. Host Features Impact on Satisfaction

Tests whether five host-level features have a measurable impact on guest satisfaction (review_scores_rating). For each feature, the analysis computes a satisfaction difference score: average rating of hosts where the feature is True minus average rating of hosts where the feature is False. The visual is a double lollipop chart with one pair of dots per feature.

**Assumptions**

- Unit of analysis is the host, not the listing. The brief explicitly says "if the host manages multiple properties, take the average score across listings", so we work against the `hosts` collection built during the common modelling step. `avg_rating` on `hosts` is the mean of `review_scores_rating` across all listings of that host.
- Hosts whose listings all have null `review_scores_rating` (so `avg_rating` is null) are excluded from the analysis. Without a satisfaction signal there is nothing to measure.
- For features where the source value can be null (`host_response_time`, `host_response_rate`), hosts with null in that feature are excluded **only from the analysis of that specific feature**. Each feature therefore has its own universe; the universes are reported in the result table.
- Per-feature mapping to binary, justified one by one:
  - `host_is_superhost`: already boolean, no mapping.
  - `host_identity_verified`: already boolean, no mapping. The brief refers to "host_is_verified"; the source field is `host_identity_verified`.
  - `is_fast_responder`: True when `host_response_time` is "within an hour" or "within a few hours"; False otherwise. The split separates hosts who reply within hours from hosts who reply within days.
  - `is_perfect_responder`: True when `host_response_rate == 100`; False otherwise. Inspecting the dataset shows that 71% of hosts with a measurable response rate sit at exactly 100, with a long left tail. The 100 vs not-100 split is the natural break in the distribution.
  - `is_flexible_cancellation`: True when `cancellation_policy` is "flexible" or "moderate"; False for "strict_14_with_grace_period", "super_strict_30" and "super_strict_60". From the guest's perspective, the flexible and moderate policies allow penalty-free cancellation in the early days; the rest are restrictive.
- When a host owns multiple listings, the binary feature value of that host is taken from the first listing encountered during the split. Inspection of the dataset confirms that hosts are consistent within their own listings for these fields, so this assumption is safe.
- The optimised pipeline (which reads the precomputed binary fields directly from the `hosts` collection) is treated as the source of truth for this analysis. The naive pipeline exists to show what the same calculation looks like without the common modelling step. Both pipelines agree exactly on `is_superhost`, `is_identity_verified` and on the count for `is_flexible_cancellation`. They diverge on the two response features because the naive pipeline picks a non-deterministic representative listing per host via the `$first` accumulator, and 698 of those representative listings happen to have a null `host_response_time` or `host_response_rate`. The naive `$cond` blocks classify those null values as `False`, inflating `n_false` by 698 for both response features. The `hosts` collection, by contrast, persists a single `is_fast_responder` and `is_perfect_responder` value per host during the split, and the `diff_score` helper correctly excludes nulls from the denominator. The Computed Pattern therefore delivers **reproducibility across pipelines** in addition to performance: every analysis built on top of `hosts` sees exactly the same value per host, instead of recomputing the mapping in flight with different non-deterministic "representative listings".
- All five binary mappings are precomputed and persisted on the `hosts` collection (`is_fast_responder`, `is_perfect_responder`, `is_flexible_cancellation`, plus the two already-boolean fields). This is the Computed Pattern from lecture 5: the values are read once per query and the mapping logic does not have to be recomputed in the aggregation pipeline.

--- CELL 82 ---
### Key findings

The optimised pipeline on the `hosts` collection is the source of truth for the numbers below.

- **Superhost is by far the strongest signal.** Hosts marked as superhost have an average rating of 96.87 against 91.94 for non-superhosts, a difference of **+4.94 points**, roughly 5x larger than any other feature in the analysis. This is consistent with the way Airbnb defines the superhost programme, which uses guest rating as one of its qualifying conditions, so part of the signal is structural.
- **Perfect responder is the second strongest.** Hosts whose response rate is exactly 100% have an average rating of 93.98 against 91.12 for hosts who miss any messages, a difference of **+2.86 points**. The split is meaningful: the dataset has a clear pile-up at exactly 100% response rate, and that group does noticeably better in satisfaction.
- **Identity verified is moderate.** Hosts with verified identity score 93.79 vs 92.79 for unverified, a difference of **+1.00 point**. Verification is a small but consistent positive signal for guests.
- **Fast responder has very little impact.** Hosts who reply within hours score 93.36 vs 92.80 for those who reply within days, a difference of **+0.56 points**. On its own, response time is barely a discriminator. Combined with the previous bullet, this suggests that *whether* the host replies (perfect responder) matters far more than *how fast* they reply once they do.
- **Cancellation policy is essentially neutral.** Hosts with flexible policies score 93.29 vs 93.13 for strict policies, a difference of **+0.10 points**. Guests do not seem to reward flexible cancellation in their ratings, possibly because most guests never need to cancel and so the policy is invisible to them.
- **Universe sizes vary by feature.** Three of the five features (`is_superhost`, `is_identity_verified`, `is_flexible_cancellation`) have full coverage on the 3797 hosts with a measurable rating. The two response features (`is_fast_responder`, `is_perfect_responder`) only cover 3099 hosts because 698 of the rated hosts have a null `host_response_time` or `host_response_rate` in the source. Each feature is reported on its own universe; comparing the diff scores across features is fair as long as the reader understands that 18% of the population is missing from the response-feature analysis.
- **The naive pipeline took 55 ms wall time against 41.5 ms for the optimised pipeline**, a 24.55% reduction. The naive does a `$match` over 5553 listings, a `$project` with two `$cond` blocks, and a blocking `$group` that aggregates 4081 listings into 3797 hosts. The optimised does a `$match` over the 5104 hosts using `idx_hosts_avg_rating` (IXSCAN with 3797 keys) and a thin `$project` to rename two fields. The wall time gain is only part of the benefit: the optimised pipeline reads a single precomputed value per host from the `hosts` collection, so every analysis built on top of it sees exactly the same number. The naive pipeline, in contrast, picks a non-deterministic representative listing per host via `$first` and classifies 698 extra hosts as `False` on the two response features - hosts whose representative listing has a null `host_response_time` or `host_response_rate`. The Computed Pattern therefore delivers reproducibility across pipelines, not just performance.
---

--- CELL 83 ---
**D3. Property Popularity and Satisfaction**

The goal of this task is to analyze how property unavailability (calculated as the complement of availability) is influenced by guest satisfaction (as indicated by review scores) for professional hosts (those managing more than one property). Assume two guests stay for one week when calculating the effective price per person per night, including any additional fees such as cleaning fees, extra person charges, or other applicable costs.

Unavailability will serve as a measure of property popularity - the more unavailable a property is, the more likely it is booked and thus is in demand. The database contains availability of the property measured in days for four different periods: next 30 days, next 60 days, next 90 days, and next 365 days. You need to suggest a way to calculate popularity based on how many days the property is unavailable in the future. 

The base assumption is that professionally rented properties can only be unavailable because they are booked. Consider adding any further attributes as weights. Keep a clear record of how you did it (a short description before the calculation cell). Based on your calculation, create a new attribute 'popularity_score' in the database. This attribute will be regularly updated in the database, so just your database design and query optimizations accordingly.

Analyze the relationship between satisfaction, and popularity by grouping properties based on guest satisfaction (review rating score, or multiple scores - your choice) in low, medium, and high satisfaction categories. Calculate and compare median popularity score for each satisfaction category. Feel free to include other considerations into this calculation.

As the result, visualize popularity scores per satisfaction category for three most common property types. Create one visual with box plots mark the range of popularity score for each satisfaction category, make sure to include min and max prices, mark the median and the range where 50 % of prices lie. 

The delivered assignment should have three components: 1. any assumptions and decisions made at the beginning, e.g. popularity score calculation. 2. one graph with 9 box plots (3 property types x 3 satisfaction categories) with distribution of popularity score. 3. result analysis and interpretation (250-350 words).

--- CELL 84 ---
---

## D3. Property Popularity and Satisfaction

Tests how property popularity (measured as unavailability) is influenced by guest satisfaction (measured as `review_scores_rating`) for professional hosts (those managing more than one property in our database).

**Assumptions**

- Universe is restricted to listings with `host_type = professional`, `review_scores.review_scores_rating != null`, and `popularity_score != null`. Without all three values there is nothing to plot.
- The `popularity_score` field is read directly from the listings collection. It was precomputed during the common modelling step from the four availability windows the dataset provides (`availability_30`, `availability_60`, `availability_90`, `availability_365`), with weights of 0.40, 0.25, 0.20 and 0.15 respectively. Shorter horizons get higher weight because near-term unavailability is a stronger signal of real bookings than the 365 day window, which is often dominated by host calendar inertia rather than actual demand. The full formula is documented in the split cell of the common modelling step.
- The brief notes that "professionally rented properties can only be unavailable because they are booked", which is the assumption that lets us treat unavailability as a proxy for popularity.
- Guest satisfaction is split into three bands using fixed cutoffs that match the qualitative bands the Airbnb platform uses internally:
  - **Low** = `review_scores_rating < 80`
  - **Medium** = `80 <= review_scores_rating < 95`
  - **High** = `review_scores_rating >= 95`
  Fixed cutoffs were chosen over data-driven cutoffs (terciles, quartiles) because they make the analysis comparable across different Airbnb extracts. The trade-off is that the Low band is the smallest of the three (35 listings in this dataset), reflecting the rating inflation typical of the platform.
- The three most common property types among the filtered universe are **Apartment** (339 listings), **Condominium** (69) and **Serviced apartment** (34). These are kept literally as the brief asks. The smaller two property types lead to small per-band sub-samples (some boxes have under 15 listings) and the interpretation flags this where relevant.
- Recurring update: the brief states `popularity_score` will be updated regularly. This is exactly why it was precomputed and persisted on the listings collection in the common modelling step (Computed Pattern). The update job only has to recompute one numerical field per listing from four availability fields; no joins, no aggregation. Indexing strategy reflects this: city + popularity descending is already in the registry from the common indexes, supporting both per-city ranking and the per-property-type filters used here.

--- CELL 88 ---
#### Key findings

The relationship between guest satisfaction and property popularity is not as monotonic as the brief implicitly suggests, and the three property types tell three different stories.

- **Apartment shows a non-monotonic pattern.** Medium-rated apartments are marginally more popular than high-rated apartments (median popularity 0.567 vs 0.527), and both are clearly more popular than low-rated apartments (0.330). The headline "high satisfaction means high popularity" therefore does not hold for the most common property type in the dataset.
- **Condominium is the only property type that follows the intuitive monotonic pattern.** High-rated condominiums have a median popularity of 0.705 against 0.543 for medium-rated. The Low band has only 1 listing and contributes nothing to the analysis. Among condominiums, higher satisfaction is associated with higher popularity, with a meaningful gap of around 0.16 points between the medium and high bands.
- **Serviced apartment is hard to interpret because of small samples.** The three bands have 6, 15 and 13 listings respectively. The medians (0.252, 0.342, 0.195) suggest a non-monotonic pattern, and the IQR for the high band is unusually wide (0.14 to 0.73), pointing to a polarised group where some serviced apartments are heavily booked and others sit empty. With only 34 listings in total, no firm conclusion is possible for this property type.
- **The Apartment non-monotonic finding deserves attention.** Two competing hypotheses can explain it. First, **price-driven saturation**: the highest-rated apartments may also be the most expensive, which depresses demand and increases availability without making them less "popular" in any deeper sense. Second, **product-segment differences**: condominiums attract a more rating-sensitive customer base than apartments, so the same satisfaction signal translates differently into bookings depending on the segment. Distinguishing between these hypotheses would require crossing the popularity measure with price and customer segment, which is outside the scope of D3.
- **Sample sizes are uneven.** Apartment has 339 listings, Condominium has 69, and Serviced apartment has 34. Within property types, the Low satisfaction band is very small for Condominium (1) and Serviced apartment (6), reflecting the rating inflation typical of the Airbnb platform. The visual is therefore most reliable for the Apartment row.
- **Recurrence and indexing.** The brief states the popularity score will be recalculated regularly. The common modelling step persists `popularity_score` on every listing during the split, so the recurring update job only has to read four availability fields per listing and overwrite one numerical field. The compound index `(address.market, popularity_score)` from the common indexes registry supports the per-city ranking that follow-up tasks (and dashboards) typically build on top of this score.

--- CELL 89 ---
# Part E - Property Features Expert

**Student:** 20250418 | Pedro Miguel Gonçalves Fernandes

This section implements all three sub-tasks of Part E using the `listings` collection built in the setup cells above.

--- CELL 90 ---
## E1 - Property Size and Pricing

### Assumptions & Decisions

1. **Cities** filtered via `address.market` ∈ `{"Hong Kong", "Montreal", "Barcelona"}`.
2. **Size categories** based on `accommodates` (max guests):
   - **Small** - 1–2 guests
   - **Medium** - 3–5 guests
   - **Large** - 6+ guests
3. **Effective price per person per night** formula:
   `(price × 7 + cleaning_fee + extra_people × max(0, accommodates − guests_included)) / (accommodates × 7)`
   - All `Decimal128` fields are cast to `float` before arithmetic.
   - `cleaning_fee` and `extra_people` default to 0 if absent.
   - `guests_included` defaults to 1 if absent.
4. **Exclusions:** listings where `price` is null, `price = 0`, or `accommodates = 0`.
5. **Write-back:** a new `size_category` attribute (`"small"`, `"medium"`, `"large"`) is written back to each qualifying listing via `bulk_write`.
6. **Outlier cap** for visualisation: prices above the 99th percentile per city are removed to keep the box plots readable.

--- CELL 94 ---
### E1 - Result Analysis

**General trend - small properties are the most expensive per person.** Across all three cities, small properties (1–2 guests) consistently show the highest median price per person per night. Fixed costs such as the cleaning fee are spread over fewer guests, and small urban apartments are often premium-priced relative to their capacity. Large properties (6+) achieve the lowest per-person cost.

**Hong Kong** stands out as the most expensive market. Its small-property median sits well above the equivalent in the other cities, reflecting extreme real-estate costs. The interquartile range is also notably wide, indicating high price dispersion.

**Barcelona** occupies a middle position. Medium-property IQR is relatively tight, suggesting homogeneous offerings in the 3–5 guest range. The large-property category has a lower median but a long upper whisker from high-end villas.

**Montreal** shows the smallest per-person prices and the most symmetric distributions, consistent with a mature, price-competitive market.

**Key takeaway:** property size is a reliable predictor of per-person cost in all three cities, with small properties commanding a substantial premium. The magnitude varies significantly by market - most pronounced in Hong Kong, least in Montreal.

--- CELL 95 ---
---

## E2 - Multi-property Ownership and Bookings

### Assumptions & Decisions

1. **Cities:** Hong Kong, Montreal, Barcelona (same filter as E1).
2. **Host classification:**
   - **Professional host** - owns > 1 listing in the `listings` collection.
   - **Amateur host** - owns exactly 1 listing.
   A Boolean field `host_type` is already computed during the data split.
3. **Booking rate score** = `number_of_reviews / months_active`, where:
   - `months_active` = max(1, `(last_review − first_review).days / 30.44`)
   - Listings with `number_of_reviews = 0` or missing review dates get `booking_rate = 0`.
4. **Write-back:** `host_type` is already set during the data split.
5. **Explain comparison:** the pipeline runs with indexes hidden (COLLSCAN baseline) vs restored (IXSCAN).

--- CELL 100 ---
### E2 - Interpretation of Results

**Professional vs Amateur booking rates.** Across all three cities, professional hosts (multi-property managers) show a **higher median booking rate** than amateur hosts. The difference is most pronounced in Barcelona and Montreal, where professional hosts achieve roughly 1.5–2× the monthly review rate of their amateur counterparts. Hong Kong shows the same directional pattern but with wider variance due to the presence of very high-volume professional operators distorting the upper tail.

This result is consistent with the hypothesis that professional hosts benefit from accumulated Airbnb experience (optimised pricing, faster response times, better listing quality) and potentially from algorithmic boosts that the platform gives to hosts with strong historical performance.

**Query optimisation.** The `explain` comparison confirms that adding the compound index `idx_market_nreviews` on `(address.market, number_of_reviews)` converts the opening `$match` stage from a full COLLSCAN to an IXSCAN. This reduces documents examined from the full collection size to only the records matching the three target markets, with a proportional reduction in execution time. The `$group` stage itself is memory-bound and not directly accelerated by the index, but the smaller input set reduces its cost as well.

--- CELL 101 ---
---

## E3 - Property Size and Property Comfort

### Assumptions & Decisions

1. **Scope:** amateur hosts only (re-using `host_type = "amateur"` from the data split); all three cities.
2. **Price per person per night:** 2 guests stay for 1 week:
   `(price × 7 + cleaning_fee + extra_people × max(0, 2 − guests_included)) / (2 × 7)`
   This is a fixed scenario (rather than max-capacity) as specified in the task.
3. **Size group** = `(bedrooms + bathrooms) / accommodates`:
   - **Small** - ratio < 0.5 (dense, low room-to-guest ratio)
   - **Medium** - 0.5 ≤ ratio ≤ 1.0
   - **Large** - ratio > 1.0 (spacious; more rooms than guests on average)
   Missing `bedrooms` or `bathrooms` are treated as 0.
4. **Comfort categories** are derived from `room_type` mapped into 5 groups:
   - `Entire home/apt` -> **Entire home**
   - `Private room` -> **Private room**
   - `Shared room` -> **Shared room**
   - `Hotel room` -> **Hotel room**
   - Anything else (or null) -> **Other / Unclassified**
   `room_type` captures the most fundamental dimension of comfort (privacy, space control) and is present in virtually every listing, making it the most reliable single attribute for comfort grouping.
5. **Satisfaction score** = `review_scores.review_scores_rating / 10` (normalised to 0–10).
   Listings missing a rating are excluded.
6. New attribute `size_group` is written back to each qualifying listing.
7. **Visualisation:** 15 box plots - for each of the 3 size groups, the 5 comfort categories are shown side by side, giving one row of 5 boxes per size group (3 rows total, laid out as 3 subplots).

--- CELL 105 ---
### E3 - Result Analysis and Interpretation

The 15 box plots examine how property spaciousness (size group) and comfort type (room type category) jointly shape guest satisfaction among amateur hosts.

**Overall satisfaction is high and narrowly spread across all groups.** Median scores cluster between 8.5 and 9.5 on a 0–10 scale regardless of size group or comfort category. This ceiling effect is common in Airbnb data - guests self-select into properties that match their expectations, and the platform's review system incentivises positive framing. As a result, the most informative signals are in the whiskers and lower outliers rather than the medians.

**Entire home listings consistently score the highest and with the least variance.** Across all three size groups, "Entire home" properties have tight interquartile ranges anchored near the top of the scale. Guests who book an entire apartment or house tend to have high satisfaction because they receive guaranteed privacy, full kitchen access, and no dependence on other guests' behaviour. This comfort advantage is independent of property size.

**Shared rooms show the lowest medians and widest spread.** In the small and medium size groups, shared rooms have noticeably more low-score outliers and longer lower whiskers, reflecting the inherent variability of the shared accommodation experience - noise, cleanliness standards, and social dynamics between strangers are hard to control. Interestingly, in the large size group, shared rooms improve slightly, possibly because larger properties offer more separation between guests.

**Hotel rooms** perform comparably to entire homes in medium and large categories, likely because they offer professional hospitality standards even when managed by an amateur host. However, hotel rooms are rare in the dataset (especially among amateur hosts), so these estimates carry higher uncertainty.

**Size group effect is subtle but present.** Medium-sized properties show marginally higher satisfaction than small properties across most comfort categories. The relationship is non-linear: very large properties do not necessarily outperform medium ones, perhaps because managing large spaces is harder for solo amateur hosts, leading to occasional lapses in maintenance or guest communication.

**Key takeaway:** comfort category (especially the entire-home advantage) is a stronger predictor of guest satisfaction than property size alone. Amateur hosts seeking to maximise satisfaction should prioritise entire-home listings regardless of size, and invest in consistent quality standards if offering shared or private-room accommodation.

