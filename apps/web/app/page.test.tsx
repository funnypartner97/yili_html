import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("offers the disabled material and template actions", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: "把材料变成可编辑成果" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "添加材料" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "选择模板" })).toBeDisabled();
  });
});
