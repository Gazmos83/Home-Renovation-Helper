import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { installMatchMedia } from "./media";

beforeEach(installMatchMedia);
