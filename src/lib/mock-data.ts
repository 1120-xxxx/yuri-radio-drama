// Mock data used when Supabase is not configured.
// Data sourced from public platform rankings (猫耳FM, 喜马拉雅, 漫播, 哔哩哔哩, 听姬).
// Replace with your own dataset or connect Supabase via environment variables.

export interface Drama {
  id: string;
  title: string;
  original_work?: string;
  platform: string;
  year: number;
  total_episodes: number;
  play_count: number;
  rating_avg: number;
  rating_count: number;
  cover_url?: string;
  description?: string;
  studio?: string;
  director?: string;
  source_url?: string;
  tags?: string[];
  is_completed?: boolean;
}

export interface Cv {
  id: string;
  name: string;
  avatar_url?: string;
  bio?: string;
}

export interface DramaCvRole {
  drama_id: string;
  cv_id: string;
  role_type: 'main' | 'support' | 'director';
  character_name?: string;
  drama_title?: string;
  cv_name?: string;
}

export interface RatingRecord {
  id: string;
  drama_id: string;
  score: number;
  comment?: string;
  ip_hash?: string;
  device_fingerprint?: string;
  created_at: string;
}

export const SAMPLE_DRAMAS: Drama[] = [
  {
    id: 'dr1',
    title: '我亲爱的法医小姐',
    original_work: '酒暖回忆',
    platform: '喜马拉雅',
    year: 2023,
    total_episodes: 80,
    play_count: 9130000,
    rating_avg: 4.8,
    rating_count: 12400,
    description: '口吐芬芳一点就炸狐狸精法医 × 前期内敛禁欲后期又奶又狼刑侦队长。查案，猜心，探情。年上，强强，双御姐。为生者权，替死者言。',
    studio: '之贝文化',
    tags: ['现代', '悬疑', '刑侦', '强强', 'HE', '高人气'],
  },
  {
    id: 'dr2',
    title: '探虚陵现代篇',
    original_work: '君sola',
    platform: '听姬',
    year: 2024,
    total_episodes: 48,
    play_count: 6850000,
    rating_avg: 4.7,
    rating_count: 8900,
    description: '师清玄与洛神，两个性格迥异的女性携手探秘，揭开一个又一个惊天谜团。',
    studio: '听姬出品',
    tags: ['现代', '悬疑', '探险', '强强', 'HE'],
  },
  {
    id: 'dr3',
    title: '我们都要好好的',
    platform: '漫播',
    year: 2024,
    total_episodes: 16,
    play_count: 300000,
    rating_avg: 4.5,
    rating_count: 3200,
    description: '漫播投喂月榜第一，漫播免费榜前5。现代百合甜宠剧。',
    studio: '壹叁贰壹工作室',
    tags: ['现代', '都市', '甜宠', 'HE', '高人气'],
  },
  {
    id: 'dr4',
    title: '夏·茉',
    platform: '猫耳FM',
    year: 2022,
    total_episodes: 3,
    play_count: 76130,
    rating_avg: 4.6,
    rating_count: 1560,
    description: '原创现代校园百合广播剧。是青春年少的情窦初开，是少年时期的别扭迷茫，是那一年盛夏的季茉。',
    studio: '山海归一工作室',
    tags: ['校园', '青春', '甜宠', 'HE'],
  },
  {
    id: 'dr5',
    title: '花期',
    platform: '猫耳FM',
    year: 2021,
    total_episodes: 1,
    play_count: 120000,
    rating_avg: 4.2,
    rating_count: 980,
    description: '一个柔软孤单的少女，一个帅气任性的女孩，两个身患绝症的女孩子在最好的年纪和最坏的时候遇到……',
    studio: 'DL_工作室',
    tags: ['现代', '虐恋', 'BE', '全一期'],
  },
  {
    id: 'dr6',
    title: '天上掉下一只小花妖',
    platform: '猫耳FM',
    year: 2019,
    total_episodes: 1,
    play_count: 64690,
    rating_avg: 4.0,
    rating_count: 640,
    description: '原创现代百合广播剧，日常轻松向。',
    tags: ['现代', '奇幻', '甜宠', '全一期'],
  },
  {
    id: 'dr7',
    title: '依旧故人来',
    platform: '喜马拉雅',
    year: 2020,
    total_episodes: 1,
    play_count: 56870,
    rating_avg: 4.1,
    rating_count: 420,
    description: '方扉求职却巧遇多年前的爱人，牵扯出一段被时间掩埋的旧情缘。多年后重逢终于冰释前嫌，谱写甜蜜篇章。',
    studio: '恶人谷配音组',
    tags: ['现代', '破镜重圆', '甜宠', 'HE', '全一期'],
  },
  {
    id: 'dr8',
    title: '如诗如梦',
    platform: '猫耳FM',
    year: 2025,
    total_episodes: 4,
    play_count: 74850,
    rating_avg: 4.3,
    rating_count: 580,
    description: '全四期百合广播剧，古风唯美。',
    tags: ['古风', '唯美', 'HE'],
  },
  {
    id: 'dr9',
    title: '漂亮废物',
    original_work: '引路星',
    platform: '猫耳FM',
    year: 2023,
    total_episodes: 14,
    play_count: 350000,
    rating_avg: 4.4,
    rating_count: 2800,
    description: '猫耳免费榜前10，持续占榜3个月。',
    studio: '壹叁贰壹工作室',
    tags: ['现代', '都市', '甜宠', 'HE'],
  },
  {
    id: 'dr10',
    title: '探虚陵古风篇',
    original_work: '君sola',
    platform: '听姬',
    year: 2023,
    total_episodes: 36,
    play_count: 5200000,
    rating_avg: 4.6,
    rating_count: 7600,
    description: '古风探秘，师清玄与洛神的前传故事，揭开千年古墓的秘密。',
    studio: '听姬出品',
    tags: ['古风', '悬疑', '探险', '强强', 'HE'],
  },
  {
    id: 'dr11',
    title: '仙尊装逼指南',
    platform: '猫耳FM',
    year: 2024,
    total_episodes: 12,
    play_count: 100000,
    rating_avg: 4.1,
    rating_count: 1200,
    description: '猫耳免费榜前30，持续霸榜2个月。',
    studio: '壹叁贰壹工作室',
    tags: ['古风', '修仙', '搞笑', 'HE'],
  },
  {
    id: 'dr12',
    title: '全网都在磕我们的CP',
    platform: '兔U',
    year: 2024,
    total_episodes: 18,
    play_count: 280000,
    rating_avg: 4.3,
    rating_count: 2100,
    description: '兔U投喂榜霸榜前5持续6个月。',
    studio: '壹叁贰壹工作室',
    tags: ['现代', '娱乐圈', '甜宠', 'HE', '高人气'],
  },
];

export const SAMPLE_CVS: Cv[] = [
  { id: 'cv1', name: '水母', bio: '代表作品：《我们都要好好的》《漂亮废物》等。声线温柔细腻，擅长现代甜宠角色。' },
  { id: 'cv2', name: '金喵儿', bio: '代表作品：《我们都要好好的》等。声线清亮，擅长御姐角色。' },
  { id: 'cv3', name: '凯特caty', bio: '代表作品：《夏·茉》等。声线可盐可甜，擅长校园青春角色。' },
  { id: 'cv4', name: '慕少寻', bio: '代表作品：《夏·茉》等。声线沉稳，擅长冷面角色。' },
  { id: 'cv5', name: '殳叶', bio: '代表作品：《花期》等。声线柔美，擅长悲剧角色。' },
  { id: 'cv6', name: '白术', bio: '代表作品：《花期》等。声线帅气，擅长中性角色。' },
  { id: 'cv7', name: '阮绡绯', bio: '代表作品：《天上掉下一只小花妖》等。声线甜美，擅长可爱角色。' },
  { id: 'cv8', name: '凤梨', bio: '代表作品：《依旧故人来》等。恶人谷配音组成员，声线百变。' },
  { id: 'cv9', name: '夏觅尘', bio: '代表作品：《全网都在磕我们的CP》等。声线低沉磁性。' },
  { id: 'cv10', name: '小K', bio: '代表作品：《漂亮废物》等。声线温柔。' },
];

export const SAMPLE_ROLES: DramaCvRole[] = [
  { drama_id: 'dr1', cv_id: 'cv1', role_type: 'main', character_name: '林厌' },
  { drama_id: 'dr1', cv_id: 'cv2', role_type: 'main', character_name: '余酒' },
  { drama_id: 'dr2', cv_id: 'cv1', role_type: 'main', character_name: '师清玄' },
  { drama_id: 'dr2', cv_id: 'cv2', role_type: 'main', character_name: '洛神' },
  { drama_id: 'dr3', cv_id: 'cv1', role_type: 'main', character_name: '主角A' },
  { drama_id: 'dr3', cv_id: 'cv2', role_type: 'main', character_name: '主角B' },
  { drama_id: 'dr4', cv_id: 'cv3', role_type: 'main', character_name: '盛夏' },
  { drama_id: 'dr4', cv_id: 'cv4', role_type: 'main', character_name: '季茉' },
  { drama_id: 'dr5', cv_id: 'cv5', role_type: 'main', character_name: '花漪' },
  { drama_id: 'dr5', cv_id: 'cv6', role_type: 'main', character_name: '郁冬' },
  { drama_id: 'dr6', cv_id: 'cv7', role_type: 'main', character_name: '林晓' },
  { drama_id: 'dr7', cv_id: 'cv8', role_type: 'main', character_name: '易水谣' },
  { drama_id: 'dr8', cv_id: 'cv7', role_type: 'main' },
  { drama_id: 'dr8', cv_id: 'cv3', role_type: 'support' },
  { drama_id: 'dr9', cv_id: 'cv10', role_type: 'main' },
  { drama_id: 'dr9', cv_id: 'cv1', role_type: 'main' },
  { drama_id: 'dr10', cv_id: 'cv1', role_type: 'main', character_name: '师清玄' },
  { drama_id: 'dr10', cv_id: 'cv2', role_type: 'main', character_name: '洛神' },
  { drama_id: 'dr11', cv_id: 'cv9', role_type: 'main' },
  { drama_id: 'dr12', cv_id: 'cv9', role_type: 'main' },
  { drama_id: 'dr12', cv_id: 'cv1', role_type: 'main' },
];
