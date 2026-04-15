"use client";
import { signIn } from "next-auth/react";

export default function SignIn() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-nadir-bg">
      <div className="card w-full max-w-md text-center">
        <h1 className="text-3xl font-bold tracking-widest text-nadir-accent mb-2">NADIR</h1>
        <p className="text-sm text-gray-400 mb-8">
          Narrative Adversarial Detection & Investment Recognition
        </p>
        <button
          onClick={() => signIn("github", { callbackUrl: "/" })}
          className="btn-primary w-full py-3 text-base"
        >
          Sign in with GitHub
        </button>
        <p className="mt-4 text-xs text-gray-600">
          Access restricted to authorized users
        </p>
      </div>
    </div>
  );
}
