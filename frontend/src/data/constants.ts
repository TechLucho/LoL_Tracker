const DD = 'https://ddragon.leagueoflegends.com/cdn/14.24.1/img'

export interface SpellInfo {
  name: string
  icon: string
}

export const SUMMONER_SPELLS: Record<number, SpellInfo> = {
  1:  { name: 'Cleanse',   icon: `${DD}/spell/SummonerBoost.png` },
  3:  { name: 'Exhaust',   icon: `${DD}/spell/SummonerExhaust.png` },
  4:  { name: 'Flash',     icon: `${DD}/spell/SummonerFlash.png` },
  6:  { name: 'Ghost',     icon: `${DD}/spell/SummonerHaste.png` },
  7:  { name: 'Heal',      icon: `${DD}/spell/SummonerHeal.png` },
  11: { name: 'Smite',     icon: `${DD}/spell/SummonerSmite.png` },
  12: { name: 'Teleport',  icon: `${DD}/spell/SummonerTeleport.png` },
  14: { name: 'Ignite',    icon: `${DD}/spell/SummonerDot.png` },
  21: { name: 'Barrier',   icon: `${DD}/spell/SummonerBarrier.png` },
}

// Data Dragon exception map: display name → URL key
const CHAMPION_KEY_MAP: Record<string, string> = {
  'Wukong': 'MonkeyKing',
  'Renata Glasc': 'Renata',
  "Cho'Gath": 'Chogath',
  "Kog'Maw": 'KogMaw',
  "Vel'Koz": 'Velkoz',
  "Rek'Sai": 'RekSai',
  'Jarvan IV': 'JarvanIV',
  'Lee Sin': 'LeeSin',
  'Master Yi': 'MasterYi',
  'Miss Fortune': 'MissFortune',
  'Xin Zhao': 'XinZhao',
  'Nunu & Willump': 'Nunu',
  'Dr. Mundo': 'DrMundo',
}

export function championKey(displayName: string): string {
  const mapped = CHAMPION_KEY_MAP[displayName]
  if (mapped) return mapped
  return displayName.replace(/[^a-zA-Z0-9]/g, '')
}

export const DDragon = {
  champion: (name: string) => `${DD}/champion/${championKey(name)}.png`,
  item: (id: number) => `${DD}/item/${id}.png`,
  spell: (id: number) => SUMMONER_SPELLS[id]?.icon ?? `${DD}/spell/SummonerFlash.png`,
}

export const QUEUE_LABELS: Record<number, string> = {
  420: 'Ranked Solo',
  400: 'Normal Draft',
  440: 'Ranked Flex',
  430: 'Normal Blind',
  900: 'URF',
  1300: 'Nexus Blitz',
}

export const IMPACT_RATINGS = [
  { value: 'Carree (1v9)', label: 'Carree (1v9)', emoji: '🔥', color: 'text-orange-400' },
  { value: 'Hice mi trabajo', label: 'Hice mi trabajo', emoji: '✅', color: 'text-emerald-400' },
  { value: 'Fui Carreado', label: 'Fui Carreado', emoji: '🚗', color: 'text-blue-400' },
  { value: 'Invisible', label: 'Invisible', emoji: '👻', color: 'text-gray-400' },
  { value: 'Inteé (Perdí la lane)', label: 'Inteé (Perdí la lane)', emoji: '💀', color: 'text-red-400' },
]

export const TILT_LEVELS = [
  { value: 1, label: 'Calma', color: 'bg-emerald-500', textColor: 'text-emerald-400' },
  { value: 2, label: 'Neutro', color: 'bg-blue-500', textColor: 'text-blue-400' },
  { value: 3, label: 'Frustrado', color: 'bg-yellow-500', textColor: 'text-yellow-400' },
  { value: 4, label: 'Tilted', color: 'bg-orange-500', textColor: 'text-orange-400' },
  { value: 5, label: 'Rage', color: 'bg-red-500', textColor: 'text-red-400' },
]
