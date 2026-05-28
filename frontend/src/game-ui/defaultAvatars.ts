import avatarBerry from "../assets/avatars/avatar-berry.svg";
import avatarLeaf from "../assets/avatars/avatar-leaf.svg";
import avatarMoon from "../assets/avatars/avatar-moon.svg";
import avatarSnow from "../assets/avatars/avatar-snow.svg";
import avatarStar from "../assets/avatars/avatar-star.svg";
import avatarSun from "../assets/avatars/avatar-sun.svg";
import emptyWolf from "../assets/avatars/empty-wolf.svg";

const DEFAULT_AVATARS = [avatarSun, avatarMoon, avatarLeaf, avatarStar, avatarSnow, avatarBerry];

export function defaultAvatarFor(seed: string | number): string {
  const raw = String(seed);
  let hash = 0;
  for (let i = 0; i < raw.length; i += 1) {
    hash = (hash * 31 + raw.charCodeAt(i)) >>> 0;
  }
  return DEFAULT_AVATARS[hash % DEFAULT_AVATARS.length];
}

export function avatarFor(avatarUrl: string | null | undefined, seed: string | number): string {
  return avatarUrl || defaultAvatarFor(seed);
}

export function emptySeatAvatar(): string {
  return emptyWolf;
}
