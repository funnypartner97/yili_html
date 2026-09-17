import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("directs visitors to the creation flow", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: "把材料变成可编辑成果" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "开始创作" })).toHaveAttribute("href", "/create");
  });
});
