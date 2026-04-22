A few real problems:

1. **n=2 is basically noise.** Two users can't tell you whether a reaction is signal or personal taste. You could ship something 60% of users will hate and both your testers happened to like it. Or kill something great because one person had a bad day.

2. **"Like" is the wrong metric.** People are polite, especially to builders. They'll say they like things they'd never actually use. Watch behavior, not opinions — did they complete the task, return, recommend it?

3. **"One objects → iterate" is asymmetric in a weird way.** One complaint blocks shipping, but one thumbs-up counts as validation? That means your decision depends heavily on *which* two users you picked.

4. **No baseline or alternative.** Liking your thing doesn't mean it's better than what they already do, or better than the simpler version you didn't build.

5. **Selection bias.** Who are these 2 users? Friends? Target segment? Random? This matters more than the test itself.

A more honest version: define what success looks like *before* testing (specific behavior, not vibes), test with ~5-8 users minimum if qualitative, look for patterns in where they struggle rather than polling opinions, and separate "is this usable" from "is this worth shipping."

That said — if this is a tiny feature and you just want a sanity check before shipping to a small audience, your plan is fine. The problem is treating 2 users as *validation* rather than as *a quick smoke test*.