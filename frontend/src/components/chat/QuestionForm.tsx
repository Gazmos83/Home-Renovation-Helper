import { useState } from "react";
import type { Question, ResumeBody } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cardClass } from "@/components/ui/card";

/**
 * A pending question set, one question at a time: the next appears only once the current
 * one has an answer, earlier ones can be revisited, and all answers go in one step. The
 * owner may decline the set and answer in their own words instead.
 */
export function QuestionForm({ questions, disabled, onAnswer, onRoomLayout }: {
  questions: Question[];
  disabled: boolean;
  onAnswer: (answer: ResumeBody) => void;
  /** Given for the placement questions: a "Room layout" button that shows the room and sends nothing. */
  onRoomLayout?: () => void;
}) {
  const [answers, setAnswers] = useState<string[]>(() => questions.map(() => ""));
  const [at, setAt] = useState(0);
  const [ownWords, setOwnWords] = useState<string | null>(null);
  const question = questions[at];
  const current = answers[at]?.trim() ?? "";
  const last = at === questions.length - 1;

  function set(value: string) {
    setAnswers((list) => list.map((a, i) => (i === at ? value : a)));
  }

  function next(value = current) {
    if (!value.trim()) return;
    if (last) onAnswer({ answers: answers.map((a, i) => (i === at ? value : a).trim()) });
    else setAt(at + 1);
  }

  if (ownWords !== null) {
    return (
      <section className={`${cardClass} mx-auto w-full max-w-xl space-y-3`} aria-label="Questions">
        <h3>Answer in your own words</h3>
        <Input aria-label="Your answer" value={ownWords} onChange={(e) => setOwnWords(e.target.value)} />
        <div className="flex gap-2">
          <Button type="button" disabled={disabled || !ownWords.trim()} onClick={() => onAnswer({ declined: ownWords.trim() })}>
            Send
          </Button>
          <Button type="button" variant="outline" onClick={() => setOwnWords(null)}>Back to the questions</Button>
        </div>
      </section>
    );
  }

  return (
    <section className={`${cardClass} mx-auto w-full max-w-xl space-y-3`} aria-label="Questions">
      <p className="text-muted-foreground">Question {at + 1} of {questions.length}</p>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          next();
        }}
      >
        {onRoomLayout && (
          <Button type="button" variant="outline" size="sm" onClick={onRoomLayout}>
            Room layout
          </Button>
        )}
        <label className="block space-y-2">
          <span className="block font-chat text-base">{question.text}</span>
          <span className="flex items-center gap-2">
            <Input aria-label={question.text} value={answers[at]} disabled={disabled} onChange={(e) => set(e.target.value)} />
            {question.unit && <span className="text-sm text-muted-foreground">{question.unit}</span>}
          </span>
        </label>
        {question.choices.length > 0 && (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Choices">
            {question.choices.map((choice) => (
              <Button
                key={choice}
                type="button"
                variant={answers[at] === choice ? "default" : "outline"}
                size="sm"
                disabled={disabled}
                onClick={() => {
                  set(choice);
                  next(choice);
                }}
              >
                {choice}
              </Button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {at > 0 && (
            <Button type="button" variant="outline" disabled={disabled} onClick={() => setAt(at - 1)}>Back</Button>
          )}
          <Button type="submit" disabled={disabled || !current}>{last ? "Send answers" : "Next"}</Button>
          <Button type="button" variant="ghost" disabled={disabled} onClick={() => setOwnWords("")}>
            Answer in my own words
          </Button>
        </div>
      </form>
    </section>
  );
}
