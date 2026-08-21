import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { WebChatGrantStore } from "../../electron/webChatGrantStore.js";

const temporaryRoots = [];

function createStoreFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "cowork-web-chat-grant-"));
  temporaryRoots.push(root);
  const workspaceA = path.join(root, "workspace-a");
  const workspaceB = path.join(root, "workspace-b");
  fs.mkdirSync(workspaceA);
  fs.mkdirSync(workspaceB);
  return {
    root,
    workspaceA,
    workspaceB,
    store: new WebChatGrantStore({ filePath: path.join(root, "web-chat-grant.json") }),
  };
}

afterEach(() => {
  for (const root of temporaryRoots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

describe("WebChatGrantStore", () => {
  it("persists one canonical workspace grant without enabling tools or a tunnel", () => {
    const { root, workspaceA, store } = createStoreFixture();

    const state = store.setGrant({
      workspacePath: workspaceA,
      workspaceName: "Workspace A",
      permissionMode: "trusted",
    });
    const reloaded = new WebChatGrantStore({ filePath: path.join(root, "web-chat-grant.json") }).getState();

    expect(state.grant).toMatchObject({ workspacePath: fs.realpathSync(workspaceA), workspaceName: "Workspace A", permissionMode: "trusted" });
    expect(reloaded.grant).toEqual(state.grant);
    expect(reloaded.toolsEnabled).toBe(false);
    expect(reloaded.tunnelConnected).toBe(false);
  });

  it("revokes the old generation before replacing a workspace or permission profile", () => {
    const { workspaceA, workspaceB, store } = createStoreFixture();
    const first = store.setGrant({ workspacePath: workspaceA, workspaceName: "A", permissionMode: "manual" });
    const second = store.setGrant({ workspacePath: workspaceB, workspaceName: "B", permissionMode: "full" });

    expect(second.grant.workspacePath).toBe(fs.realpathSync(workspaceB));
    expect(second.grant.id).not.toBe(first.grant.id);
    expect(second.revision).toBe(first.revision + 2);

    const revoked = store.revoke();
    expect(revoked.grant).toBeNull();
    expect(revoked.revision).toBe(second.revision + 1);
  });

  it("rejects invalid permission modes and paths that are not real directories", () => {
    const { root, workspaceA, store } = createStoreFixture();

    expect(() => store.setGrant({ workspacePath: workspaceA, permissionMode: "anything" })).toThrow(/permission/i);
    expect(() => store.setGrant({ workspacePath: path.join(root, "missing"), permissionMode: "manual" })).toThrow(/directory/i);
    expect(() => store.setGrant({ workspacePath: path.join(root, "web-chat-grant.json"), permissionMode: "manual" })).toThrow(/directory/i);
  });
});
