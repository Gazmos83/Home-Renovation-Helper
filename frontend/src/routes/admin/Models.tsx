import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

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

  if (!models.data) return <Page>Loading…</Page>;
  const entries = models.data.registry.filter((row) => row.slug);

  return (
    <Page>
      <h1>Models and routing</h1>
      {models.data.slots.map((slot) => (
        <section key={slot.slot} className={cardClass}>
          <h2>
            {slot.slot} {slot.override ? "(override)" : ""}
          </h2>
          <Label htmlFor={`route-${slot.slot}`}>Model</Label>
          <Select
            id={`route-${slot.slot}`}
            value={slot.model}
            onChange={(event) => route.mutate({ slot: slot.slot, model: event.target.value })}
          >
            {entries.map((entry) => (
              <option key={entry.slug} value={entry.slug}>
                {entry.alias ? `${entry.slug} (alias — follows the newest V4 Flash)` : entry.slug}
              </option>
            ))}
          </Select>
          {errors[`route-${slot.slot}`] && <p className="text-sm text-destructive">{errors[`route-${slot.slot}`]}</p>}
        </section>
      ))}
      <h1>Generation and budgets</h1>
      {models.data.models.map((model) => (
        <section key={model.slug} className={cardClass}>
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
            <Label htmlFor={`context-${model.slug}`}>Context budget</Label>
            <Input
              id={`context-${model.slug}`}
              name="context"
              type="number"
              defaultValue={model.context_budget_tokens}
            />
            {errors[`budget-${model.slug}-context_budget_tokens`] && (
              <p className="text-sm text-destructive">{errors[`budget-${model.slug}-context_budget_tokens`]}</p>
            )}
            <Label htmlFor={`daily-${model.slug}`}>Daily ceiling</Label>
            <Input id={`daily-${model.slug}`} name="daily" type="number" defaultValue={model.daily_token_ceiling} />
            {errors[`budget-${model.slug}-daily_token_ceiling`] && (
              <p className="text-sm text-destructive">{errors[`budget-${model.slug}-daily_token_ceiling`]}</p>
            )}
            <p>
              <Button type="submit">Save budget</Button>
            </p>
          </form>
        </section>
      ))}
    </Page>
  );
}
