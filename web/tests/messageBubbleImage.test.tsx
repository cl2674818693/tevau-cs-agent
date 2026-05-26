import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ImageThumb } from "../src/components/ImageThumb";

describe("ImageThumb", () => {
  it("renders an img with given src", () => {
    render(<ImageThumb src="/api/v1/conversations/1/attachments/5" />);
    expect(screen.getByRole("img").getAttribute("src")).toBe(
      "/api/v1/conversations/1/attachments/5",
    );
  });
});
