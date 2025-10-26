import server, {HTTP_METHODS} from "./server";
import {IAccount, IMedia, IMediaPart, IPost} from "../types/entities";

/* Media Part */
export const deleteMediaPart = async (mediaPartId: number): Promise<void> => {
    return await server.post("media_part/" + mediaPartId, {}, HTTP_METHODS.delete);
}

export const saveMediaPart = async (mediaPart: IMediaPart): Promise<void> => {
    return await server.post("media_part/", mediaPart);
}

/* Media */
export const saveMediaAnnotations = async (media: IMedia): Promise<void> => {
    return await server.post("media/", {
        notes: media.notes,
        tags: media.tags,
    });
}

/* Post */
export const savePostAnnotations = async (post: IPost): Promise<void> => {
    return await server.post("post/", {
        notes: post.notes,
        tags: post.tags,
    });
}

/* Account */
export const saveAccountAnnotations = async (account: IAccount): Promise<void> => {
    return await server.post("account/", {
        notes: account.notes,
        tags: account.tags,
    });
}