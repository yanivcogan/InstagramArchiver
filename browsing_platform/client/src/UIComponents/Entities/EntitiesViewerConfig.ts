// fallow-ignore-file unused-class-members
import React from "react";

type IEntityDisplayOption = "display" | "hide" | "collapse";
type IEntityAnnotatorOption = "show" | "hide" | "disable";
type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

interface IEntityViewerConfig {
    all: {
        hideInnerLinks?: boolean;
    }
    account: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        postsPageSize?: number | null;
    }
    post: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        compactMode?: boolean;
    }
    media: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        style?: React.CSSProperties;
    }
    mediaPart: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        style?: React.CSSProperties;
    }
    archivingSession: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    comment: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    postLike: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    taggedAccount: {
        display: IEntityDisplayOption;
    }
    accountRelation: {
        display: IEntityDisplayOption;
    }
}

export class EntityViewerConfig implements IEntityViewerConfig {
    // fallow-ignore-next-line unused-class-members
    all = {
        hideInnerLinks: false
    }
    // fallow-ignore-next-line unused-class-members
    account = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        postsPageSize: null
    };
    // fallow-ignore-next-line unused-class-members
    post = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        compactMode: false,
    };
    // fallow-ignore-next-line unused-class-members
    media = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        style: {} as React.CSSProperties,
    };
    // fallow-ignore-next-line unused-class-members
    mediaPart = {
        display: "hide" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        style: {} as React.CSSProperties,
    };
    // fallow-ignore-next-line unused-class-members
    archivingSession = {
        display: "hide" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    // fallow-ignore-next-line unused-class-members
    comment = {
        display: "hide" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    // fallow-ignore-next-line unused-class-members
    postLike = {
        display: "hide" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    // fallow-ignore-next-line unused-class-members
    taggedAccount = {
        display: "display" as IEntityDisplayOption,
    };
    // fallow-ignore-next-line unused-class-members
    accountRelation = {
        display: "display" as IEntityDisplayOption,
    };

    constructor(config?: DeepPartial<IEntityViewerConfig>) {
        if (config) {
            Object.keys(config).forEach((key) => {
                if (this.hasOwnProperty(key) && config[key as keyof IEntityViewerConfig]) {
                    Object.assign(this[key as keyof EntityViewerConfig], config[key as keyof IEntityViewerConfig]);
                }
            });
        }
    }
}