A few real problems:

1. **Two users is not a signal.** With n=2, "both like it" could easily be noise — friends being polite, people who self-selected into testing, or users who happen to match each other. You can't distinguish "good feature" from "got lucky twice."

2. **"Like it" is the wrong metric.** People say they like things they won't use. Watch behavior (do they reach for it unprompted? does it solve the problem they came with?) rather than asking for approval.

3. **The asymmetry is backwards.** You're treating 2 approvals as green light but 1 objection as just "iterate." One thoughtful objection often contains more information than two casual approvals — especially if the objector articulates *why*. Don't flatten that into a vote count.

4. **No kill criterion.** What does "iterate" mean? How many cycles before you admit the feature is wrong? Without a stopping rule, you'll iterate forever on something that should've been scrapped.

5. **Selection bias in the testers.** Who are these 2 users? If they're engaged power users or people close to you, their reaction tells you nothing about the median user who'll actually encounter the feature in the wild.

What would actually work better: decide *in advance* what behavior (not opinion) would count as success, test with enough people that a single polite "yeah it's cool" doesn't dominate, and write down what you'd have to see to kill it.

What's the feature? The right sample size and metric depends on what you're building.