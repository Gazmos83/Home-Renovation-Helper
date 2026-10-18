import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { ApprovalRow } from "./ApprovalRow";

function show(props: { approved: boolean; built: boolean; pending?: boolean; error?: string | null }) {
  const onApprove = vi.fn();
  const onUnapprove = vi.fn();
  render(
    <ApprovalRow
      label="Approval"
      version={2}
      approved={props.approved}
      built={props.built}
      pending={props.pending ?? false}
      error={props.error ?? null}
      onApprove={onApprove}
      onUnapprove={onUnapprove}
    />,
  );
  return { onApprove, onUnapprove };
}

test("a built version that is not approved offers approve", async () => {
  const { onApprove } = show({ approved: false, built: true });
  expect(screen.getByText("Version 2 is not approved.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Unapprove version 2" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Approve version 2" }));
  expect(onApprove).toHaveBeenCalled();
});

test("an approved version shows the badge and offers unapprove", async () => {
  const { onUnapprove } = show({ approved: true, built: true });
  expect(screen.getByText("Approved")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve version 2" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Unapprove version 2" }));
  expect(onUnapprove).toHaveBeenCalled();
});

test("a version that is not built offers no control", () => {
  show({ approved: false, built: false });
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("the controls are disabled while a change is pending, and a refusal is shown", () => {
  show({ approved: false, built: true, pending: true, error: "version 2 must be built before it can be approved" });
  expect(screen.getByRole("button", { name: "Approve version 2" })).toBeDisabled();
  expect(screen.getByText("version 2 must be built before it can be approved")).toBeInTheDocument();
});
