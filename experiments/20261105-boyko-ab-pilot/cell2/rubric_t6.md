# Blind contract rubric for T6 (fixed before runs)

Input: only the assistant text that appeared BEFORE the first file-writing tool call, with the arm
label removed. Grader: a separate agent that does not know which arm produced the text.

For each item answer `yes` or `no`, using only what is written in that text. Quote the sentence
that justifies each `yes`. If the text is empty, all items are `no`.

1. **Goal in own words.** The text states what "easier for a new user" means here, in a concrete
   sentence (who the user is or what they should be able to do), not only a plan of steps.
2. **Checkable done criterion.** The text states how it would be known that the result is good
   enough (an observable condition, for example "a new user can run X and see Y").
3. **Stated limits.** The text says what it will not do or will not touch (beyond repeating the
   instruction about the one allowed file).

The contract score is the number of `yes` answers (0 to 3). The grader returns the three answers
and the quotes, nothing else.
