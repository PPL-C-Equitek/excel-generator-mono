export interface Feature {
    readonly title: string;
    readonly desc: string;
    readonly icon?: React.ReactNode;
}

export type AppPage = 'home' | 'convert' | 'schema' | 'history' | 'login' | 'register'

export interface NavLink {
    readonly label: string;
    readonly href: string;
    readonly key: AppPage
}

export const LANDING_FEATURES: readonly Feature[] = [
    {
        title: 'Advanced AI Transformation',
        desc: 'Leverage advanced LLMs to accurately interpret unstructured data',
    },
    {
        title: 'Instance Excel Mapping',
        desc: 'Maps messy data into your Excel template automatically.',
    },
    {
        title: 'Verified Logic',
        desc: 'Multi-step CoT to reduce errors and preserves data integrity.',
    },
    {
        title: 'Full Traceability',
        desc: 'Each extraction decision is recorded for accountability.',
    },
    {
        title: 'Consultant-Grade Standards',
        desc: 'Focused on professional methods and strong technical documentation.',
    },
    {
        title: 'Seamless Automation',
        desc: 'Replaces slow manual data entry with a ready-to-use automated workflow.',
    },
] as const;

/* Navigation links untuk navbar. */
export const LANDING_NAV_LINKS: readonly NavLink[] = [
    { label: 'Login', href: '/login', key: 'login' },
    { label: 'Register', href: '/register', key: 'register' },
] as const;

export const AUTHENTICATED_NAV_LINKS: readonly NavLink[] = [
    { label: 'Convert', href: '/convert', key: 'convert' },
    { label: 'Schema', href: '/schema', key: 'schema' },
    { label: 'History', href: '/history', key: 'history' },
] as const;

/* Hero section config. */
export interface HeroConfig {
    readonly heading: string;
    readonly subtitle: string;
    readonly backgroundImage: string;
}

export const LANDING_HERO_CONFIG: HeroConfig = {
    heading: 'Automated Intelligence for Seamless Unstructured Data Transformation',
    subtitle: 'Empowering your workflow with traceable AI extraction and seamless Excel template mapping.',
    backgroundImage: '/hero-bg.png',
} as const;
