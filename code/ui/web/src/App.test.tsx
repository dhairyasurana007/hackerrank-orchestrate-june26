import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";

beforeEach(() => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      json: () =>
        Promise.resolve({
          claims: [
            {
              index: 0,
              user_id: "user_001",
              claim_object: "car",
              user_claim: "rear bumper dent",
              image_ids: ["img_1"],
              image_paths: ["images/test/case_001/img_1.jpg"],
              labels: {},
            },
          ],
        }),
    }),
  ) as unknown as typeof fetch;
});

test("renders claims from the API", async () => {
  render(<App />);
  expect(screen.getByText("Evidence Review Dashboard")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("user_001")).toBeTruthy());
});
