import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../../lib/api";

export default function Models() {
  const queryClient = useQueryClient();
  const models = useQuery({ queryKey: ["admin-models"], queryFn: api.models });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const route = useMutation({
    mutationFn: ({ slot, model }: { slot: string; model: string }) => api.setRouting(slot, model),
    onSuccess: () => {
      setErrors({});
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
    },
    onError: (error: Error, variables) => {
      const field = error instanceof ApiError ? error.field ?? "model" : "model";
      setErrors({ [`route-${variables.slot}`]: error.message, field });
    },
  });

  const budget = useMutation({
    mutationFn: ({
      slug,
      context_budget_tokens,
      daily_token_ceiling,
    }: {
      slug: string;
      context_budget_tokens: number;
      daily_token_ceiling: number;
    }) => api.setBudget(slug, context_budget_tokens, daily_token_ceiling),
    onSuccess: () => {
      setErrors({});
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
    },
    onError: (error: Error, variables) => {
      const field = error instanceof ApiError ? error.field ?? "daily_token_ceiling" : "daily_token_ceiling";
      setErrors({ [`budget-${variables.slug}-${field}`]: error.message, field });
    },
  });

  if (!models.data) return <main>Loading…</main>;
  const slugs = models.data.registry.filter((row) => row.slug).map((row) => row.slug);

  return (
    <main>
      <h1>Models and routing</h1>
      {models.data.slots.map((slot) => (
        <section key={slot.slot} className="card">
          <h2>
            {slot.slot} {slot.override ? "(override)" : ""}
          </h2>
          <label htmlFor={`route-${slot.slot}`}>Model</label>
          <select
            id={`route-${slot.slot}`}
            value={slot.model}
            onChange={(event) => route.mutate({ slot: slot.slot, model: event.target.value })}
          >
            {slugs.map((slug) => (
              <option key={slug} value={slug}>
                {slug}
              </option>
            ))}
          </select>
          {errors[`route-${slot.slot}`] && <p className="error">{errors[`route-${slot.slot}`]}</p>}
        </section>
      ))}
      <h1>Generation and budgets</h1>
      {models.data.models.map((model) => (
        <section key={model.slug} className="card">
          <h2>{model.slug}</h2>
          <p>Today: {model.usage_today} tokens</p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const context = Number(new FormData(form).get("context"));
              const daily = Number(new FormData(form).get("daily"));
              budget.mutate({ slug: model.slug, context_budget_tokens: context, daily_token_ceiling: daily });
            }}
          >
            <label htmlFor={`context-${model.slug}`}>Context budget</label>
            <input
              id={`context-${model.slug}`}
              name="context"
              type="number"
              defaultValue={model.context_budget_tokens}
            />
            {errors[`budget-${model.slug}-context_budget_tokens`] && (
              <p className="error">{errors[`budget-${model.slug}-context_budget_tokens`]}</p>
            )}
            <label htmlFor={`daily-${model.slug}`}>Daily ceiling</label>
            <input id={`daily-${model.slug}`} name="daily" type="number" defaultValue={model.daily_token_ceiling} />
            {errors[`budget-${model.slug}-daily_token_ceiling`] && (
              <p className="error">{errors[`budget-${model.slug}-daily_token_ceiling`]}</p>
            )}
            <p>
              <button type="submit">Save budget</button>
            </p>
          </form>
        </section>
      ))}
    </main>
  );
}
