const KEY_DONE = "loggator_onboarding_v1_done";
const KEY_STEP = "loggator_onboarding_v1_step";

export function onboardingDoneKey(userSub: string) {
  return `${KEY_DONE}:${userSub}`;
}

export function onboardingStepKey(userSub: string) {
  return `${KEY_STEP}:${userSub}`;
}

export function isOnboardingComplete(userSub: string): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(onboardingDoneKey(userSub)) === "1";
}

export function setOnboardingComplete(userSub: string) {
  window.localStorage.setItem(onboardingDoneKey(userSub), "1");
}

export function getOnboardingStep(userSub: string): number {
  if (typeof window === "undefined") return 0;
  const raw = window.localStorage.getItem(onboardingStepKey(userSub));
  const n = raw ? parseInt(raw, 10) : 0;
  return Number.isFinite(n) ? n : 0;
}

export function setOnboardingStep(userSub: string, step: number) {
  window.localStorage.setItem(onboardingStepKey(userSub), String(step));
}
